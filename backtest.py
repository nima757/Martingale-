from dataclasses import dataclass
from typing import Callable, Optional
import pandas as pd
import numpy as np

@dataclass
class BacktestConfig:
    move_pct: float = 0.10
    legs: int = 4
    leg_max_minutes: int = 15
    pattern_max_minutes: int = 120
    tolerance_pct: float = 0.01
    activation_pct: float = 0.10
    trail_pct: float = 0.10
    max_trade_minutes: int = 240
    start_bet: float = 10.0
    max_bet: float = 100000.0
    multiplier: float = 2.0
    reset_on_profit: bool = True
    direction: str = "both"

def prepare(df):
    x = df.copy()
    lower = {str(c).strip().lower(): c for c in x.columns}
    dt = next((lower[k] for k in ("datetime","date","timestamp") if k in lower), None)
    if dt is None:
        raise ValueError("CSV braucht eine datetime/date/timestamp-Spalte.")
    for k in ("open","high","low","close"):
        if k not in lower:
            raise ValueError(f"CSV braucht die Spalte '{k}'.")
    x = x.rename(columns={lower[k]: k for k in ("open","high","low","close")})
    x["datetime"] = pd.to_datetime(x[dt], errors="coerce")
    for c in ("open","high","low","close"):
        x[c] = pd.to_numeric(x[c], errors="coerce")
    return (x.dropna(subset=["datetime","open","high","low","close"])
             .sort_values("datetime").drop_duplicates("datetime").reset_index(drop=True))

def find_signals(df, cfg, progress: Optional[Callable[[int],None]]=None):
    n=len(df)
    if n < cfg.legs+2: return []
    target=max(0.0,cfg.move_pct/100-cfg.tolerance_pct/100)
    max_leg=pd.Timedelta(minutes=cfg.leg_max_minutes)
    max_pattern=pd.Timedelta(minutes=cfg.pattern_max_minutes)
    times=df.datetime.to_numpy(); hi=df.high.to_numpy(float); lo=df.low.to_numpy(float); cl=df.close.to_numpy(float)
    dirs=[1,-1] if cfg.direction=="both" else ([1] if cfg.direction=="long" else [-1])
    out=[]; seen=set()
    for i in range(n-1):
        if progress and i % max(1,n//100)==0: progress(int(i/n*100))
        for d in dirs:
            last=i; count=0; j=i+1
            while j<n and times[j]-times[i] <= max_pattern and times[j]-times[last] <= max_leg:
                move=(hi[j]/cl[last]-1) if d==1 else (1-lo[j]/cl[last])
                if move>=target:
                    count+=1; last=j
                    if count>=cfg.legs and last+1<n:
                        key=(last+1,d)
                        if key not in seen:
                            seen.add(key)
                            out.append({"entry_idx":last+1,"direction":d,
                                        "pattern_start":pd.Timestamp(times[i]),
                                        "pattern_end":pd.Timestamp(times[last])})
                        break
                j+=1
    if progress: progress(100)
    return out

def simulate_trade(df,sig,cfg):
    e=sig["entry_idx"]; d=sig["direction"]; entry=float(df.at[e,"open"])
    activation=entry*(1+d*cfg.activation_pct/100); deadline=df.at[e,"datetime"]+pd.Timedelta(minutes=cfg.max_trade_minutes)
    active=False; peak=entry; stop=None
    for k in range(e,len(df)):
        if df.at[k,"datetime"]>deadline:
            x=max(e,k-1); close=float(df.at[x,"close"])
            return _row(df,sig,e,x,entry,close,d*(close-entry)/entry*100,"timeout",active)
        high,low=float(df.at[k,"high"]),float(df.at[k,"low"])
        if d==1:
            if not active and high>=activation: active=True; peak=high; stop=peak*(1-cfg.trail_pct/100)
            elif active and high>peak: peak=high; stop=peak*(1-cfg.trail_pct/100)
            if active and low<=stop:
                return _row(df,sig,e,k,entry,stop,(stop-entry)/entry*100,"trailing_stop",True)
        else:
            if not active and low<=activation: active=True; peak=low; stop=peak*(1+cfg.trail_pct/100)
            elif active and low<peak: peak=low; stop=peak*(1+cfg.trail_pct/100)
            if active and high>=stop:
                return _row(df,sig,e,k,entry,stop,(entry-stop)/entry*100,"trailing_stop",True)
    x=len(df)-1; close=float(df.at[x,"close"])
    return _row(df,sig,e,x,entry,close,d*(close-entry)/entry*100,"end_of_data",active)

def _row(df,sig,e,x,entry,exit_price,ret,reason,active):
    return {"entry_time":df.at[e,"datetime"],"exit_time":df.at[x,"datetime"],
            "direction":"Long" if sig["direction"]==1 else "Short","entry":entry,"exit":exit_price,
            "return_pct":ret,"exit_reason":reason,"activated":active,"pattern_end":sig["pattern_end"]}

def run_backtest(df,cfg,progress=None):
    df=prepare(df); signals=find_signals(df,cfg,progress)
    rows=[]; bet=cfg.start_bet; equity=peak=max_dd=0.0; streak=max_streak=0
    for i,sig in enumerate(signals):
        tr=simulate_trade(df,sig,cfg); pnl=bet*tr["return_pct"]/100
        tr.update(bet_eur=bet,pnl_eur=pnl)
        equity+=pnl; peak=max(peak,equity); max_dd=max(max_dd,peak-equity)
        if pnl>0:
            streak=0; bet=cfg.start_bet if cfg.reset_on_profit else min(cfg.max_bet,bet*cfg.multiplier)
        else:
            streak+=1; max_streak=max(max_streak,streak); bet=min(cfg.max_bet,bet*cfg.multiplier)
        tr["equity_eur"]=equity; rows.append(tr)
        if progress and i%max(1,len(signals)//100 or 1)==0: progress(int(i/max(1,len(signals))*100))
    if progress: progress(100)
    t=pd.DataFrame(rows)
    return t, {"trades":len(t),"net_profit_eur":float(t.pnl_eur.sum()) if len(t) else 0.0,
               "win_rate_pct":float((t.pnl_eur>0).mean()*100) if len(t) else 0.0,
               "max_bet_eur":float(t.bet_eur.max()) if len(t) else 0.0,
               "max_loss_streak":int(max_streak),"max_drawdown_eur":float(max_dd)}

def run_parameter_sweep(df,patterns,stops,base_cfg,progress=None):
    combos=[(p,s) for p in patterns for s in stops]; result=[]
    for i,(p,s) in enumerate(combos):
        cfg=BacktestConfig(**{**base_cfg.__dict__,"legs":int(p["legs"]),"move_pct":float(p["move_pct"]),
                              "activation_pct":float(s["activation_pct"]),"trail_pct":float(s["trail_pct"])})
        _,st=run_backtest(df,cfg)
        result.append({"Muster":f'{cfg.legs}×{cfg.move_pct:.2f}%',"Aktivierung":f'{cfg.activation_pct:.2f}%',
                       "Trailing":f'{cfg.trail_pct:.2f}%',**st})
        if progress: progress(int((i+1)/len(combos)*100))
    return pd.DataFrame(result)
