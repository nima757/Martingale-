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
    initial_stop_pct: float = 0.20
    activation_pct: float = 0.10
    trail_pct: float = 0.10
    max_trade_minutes: int = 240
    start_risk: float = 10.0
    max_risk: float = 100000.0
    multiplier: float = 2.0
    max_martingale_steps: int = 7
    reset_on_profit: bool = True
    direction: str = "both"

def prepare(df):
    x=df.copy()
    lower={str(c).strip().lower():c for c in x.columns}
    dt=next((lower[k] for k in ("datetime","date","timestamp") if k in lower),None)
    if dt is None: raise ValueError("CSV braucht datetime/date/timestamp.")
    for k in ("open","high","low","close"):
        if k not in lower: raise ValueError(f"CSV braucht '{k}'.")
    x=x.rename(columns={lower[k]:k for k in ("open","high","low","close")})
    x["datetime"]=pd.to_datetime(x[dt],errors="coerce")
    for c in ("open","high","low","close"): x[c]=pd.to_numeric(x[c],errors="coerce")
    return x.dropna(subset=["datetime","open","high","low","close"]).sort_values("datetime").drop_duplicates("datetime").reset_index(drop=True)

def find_signals(df,cfg,progress:Optional[Callable[[int],None]]=None):
    n=len(df)
    if n<cfg.legs+2:return []
    target=max(0,cfg.move_pct/100-cfg.tolerance_pct/100)
    maxleg=pd.Timedelta(minutes=cfg.leg_max_minutes); maxpat=pd.Timedelta(minutes=cfg.pattern_max_minutes)
    t=df.datetime.to_numpy(); h=df.high.to_numpy(float); l=df.low.to_numpy(float); c=df.close.to_numpy(float)
    dirs=[1,-1] if cfg.direction=="both" else ([1] if cfg.direction=="long" else [-1])
    out=[];seen=set()
    for i in range(n-1):
        if progress and i%max(1,n//100)==0: progress(int(i/n*100))
        for d in dirs:
            last=i;count=0;j=i+1
            while j<n and t[j]-t[i]<=maxpat and t[j]-t[last]<=maxleg:
                mv=(h[j]/c[last]-1) if d==1 else (1-l[j]/c[last])
                if mv>=target:
                    count+=1;last=j
                    if count>=cfg.legs and last+1<n:
                        key=(last+1,d)
                        if key not in seen:
                            seen.add(key);out.append({"entry_idx":last+1,"direction":d,"pattern_start":pd.Timestamp(t[i]),"pattern_end":pd.Timestamp(t[last])})
                        break
                j+=1
    if progress:progress(100)
    return out

def simulate_trade(df,sig,cfg):
    e=sig["entry_idx"];d=sig["direction"];entry=float(df.at[e,"open"])
    deadline=df.at[e,"datetime"]+pd.Timedelta(minutes=cfg.max_trade_minutes)
    if d==1: init_stop=entry*(1-cfg.initial_stop_pct/100); activation=entry*(1+cfg.activation_pct/100)
    else: init_stop=entry*(1+cfg.initial_stop_pct/100); activation=entry*(1-cfg.activation_pct/100)
    active=False;peak=entry;stop=init_stop
    for k in range(e,len(df)):
        if df.at[k,"datetime"]>deadline:
            x=max(e,k-1);close=float(df.at[x,"close"]);ret=d*(close-entry)/entry*100
            return _row(df,sig,e,x,entry,close,ret,"timeout",active,False)
        hi=float(df.at[k,"high"]);lo=float(df.at[k,"low"])
        if d==1:
            # Conservative rule if initial stop and activation are both touched in one candle:
            if not active and lo<=init_stop: return _row(df,sig,e,k,entry,init_stop,(init_stop-entry)/entry*100,"initial_stop",False,True)
            if not active and hi>=activation:
                active=True;peak=hi;stop=peak*(1-cfg.trail_pct/100)
            elif active and hi>peak:
                peak=hi;stop=peak*(1-cfg.trail_pct/100)
            if active and lo<=stop:return _row(df,sig,e,k,entry,stop,(stop-entry)/entry*100,"trailing_stop",True,True)
        else:
            if not active and hi>=init_stop:return _row(df,sig,e,k,entry,init_stop,(entry-init_stop)/entry*100,"initial_stop",False,True)
            if not active and lo<=activation:
                active=True;peak=lo;stop=peak*(1+cfg.trail_pct/100)
            elif active and lo<peak:
                peak=lo;stop=peak*(1+cfg.trail_pct/100)
            if active and hi>=stop:return _row(df,sig,e,k,entry,stop,(entry-stop)/entry*100,"trailing_stop",True,True)
    x=len(df)-1;close=float(df.at[x,"close"]);ret=d*(close-entry)/entry*100
    return _row(df,sig,e,x,entry,close,ret,"end_of_data",active,False)

def _row(df,sig,e,x,entry,exit_price,ret,reason,active,stopped):
    return {"entry_time":df.at[e,"datetime"],"exit_time":df.at[x,"datetime"],"direction":"Long" if sig["direction"]==1 else "Short",
            "entry":entry,"exit":exit_price,"return_pct":ret,"exit_reason":reason,"activated":active,"stopped":stopped,"pattern_end":sig["pattern_end"]}

def run_backtest(df,cfg,progress=None):
    df=prepare(df);signals=find_signals(df,cfg,progress)
    rows=[];risk=cfg.start_risk;step=0;equity=peak=maxdd=0.;streak=maxstreak=0
    for i,s in enumerate(signals):
        tr=simulate_trade(df,s,cfg)
        # Risk-based position sizing: risk is the maximum planned loss at initial stop.
        stop_pct=max(cfg.initial_stop_pct,1e-9)/100
        notional=risk/stop_pct
        pnl=notional*tr["return_pct"]/100
        tr.update(risk_eur=risk,notional_eur=notional,pnl_eur=pnl,martingale_step=step)
        equity+=pnl;peak=max(peak,equity);maxdd=max(maxdd,peak-equity)
        if pnl>0:
            streak=0
            risk=cfg.start_risk if cfg.reset_on_profit else min(cfg.max_risk,risk*cfg.multiplier)
            step=0 if cfg.reset_on_profit else min(cfg.max_martingale_steps,step+1)
        else:
            streak+=1;maxstreak=max(maxstreak,streak)
            if step>=cfg.max_martingale_steps:
                risk=cfg.start_risk;step=0
            else:
                risk=min(cfg.max_risk,risk*cfg.multiplier);step+=1
        tr["equity_eur"]=equity;rows.append(tr)
        if progress and i%max(1,len(signals)//100 or 1)==0:progress(int(i/max(1,len(signals))*100))
    if progress:progress(100)
    t=pd.DataFrame(rows)
    stats={"trades":len(t),"net_profit_eur":float(t.pnl_eur.sum()) if len(t) else 0.,
           "win_rate_pct":float((t.pnl_eur>0).mean()*100) if len(t) else 0.,
           "max_risk_eur":float(t.risk_eur.max()) if len(t) else 0.,
           "max_notional_eur":float(t.notional_eur.max()) if len(t) else 0.,
           "max_loss_streak":int(maxstreak),"max_drawdown_eur":float(maxdd)}
    return t,stats

def run_parameter_sweep(df,patterns,stops,base_cfg,progress=None):
    combos=[(p,s) for p in patterns for s in stops];res=[]
    for i,(p,s) in enumerate(combos):
        cfg=BacktestConfig(**{**base_cfg.__dict__,"legs":int(p["legs"]),"move_pct":float(p["move_pct"]),
          "initial_stop_pct":float(s["initial_stop_pct"]),"activation_pct":float(s["activation_pct"]),"trail_pct":float(s["trail_pct"])})
        _,st=run_backtest(df,cfg)
        res.append({"Muster":f'{cfg.legs}×{cfg.move_pct:.2f}%',"Initial Stop":f'{cfg.initial_stop_pct:.2f}%',
                    "Aktivierung":f'{cfg.activation_pct:.2f}%',"Trailing":f'{cfg.trail_pct:.2f}%',**st})
        if progress:progress(int((i+1)/len(combos)*100))
    return pd.DataFrame(res)
