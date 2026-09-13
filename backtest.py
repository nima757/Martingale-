
from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd

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
    cols = {c.lower(): c for c in x.columns}
    dt = cols.get("datetime") or cols.get("date") or cols.get("timestamp")
    if not dt:
        raise ValueError("CSV benötigt eine datetime/date/timestamp-Spalte.")
    x["datetime"] = pd.to_datetime(x[dt], errors="coerce")
    rename = {}
    for target in ["open", "high", "low", "close"]:
        src = cols.get(target)
        if not src:
            raise ValueError(f"CSV benötigt die Spalte {target}.")
        rename[src] = target
    x = x.rename(columns=rename)
    x = x.dropna(subset=["datetime","open","high","low","close"]).sort_values("datetime").reset_index(drop=True)
    return x[["datetime","open","high","low","close"]]

def find_signals(df, cfg):
    signals = []
    n = len(df)
    target = cfg.move_pct / 100.0
    tol = cfg.tolerance_pct / 100.0
    dirs = [1, -1] if cfg.direction == "both" else ([1] if cfg.direction == "long" else [-1])

    for i in range(n - 1):
        for direction in dirs:
            anchor = float(df.at[i, "close"])
            last_idx = i
            legs_done = 0
            first_ts = df.at[i, "datetime"]
            for j in range(i + 1, n):
                if (df.at[j, "datetime"] - first_ts).total_seconds() > cfg.pattern_max_minutes * 60:
                    break
                base = float(df.at[last_idx, "close"])
                if direction == 1:
                    reached = float(df.at[j, "high"]) >= base * (1 + target - tol)
                else:
                    reached = float(df.at[j, "low"]) <= base * (1 - target + tol)
                if reached:
                    legs_done += 1
                    last_idx = j
                    if legs_done >= cfg.legs:
                        entry_idx = last_idx + 1
                        if entry_idx < n:
                            signals.append({
                                "signal_idx": i,
                                "pattern_end_idx": last_idx,
                                "entry_idx": entry_idx,
                                "direction": direction,
                                "pattern_start": first_ts,
                                "pattern_end": df.at[last_idx, "datetime"],
                            })
                        break
                elif (df.at[j, "datetime"] - df.at[last_idx, "datetime"]).total_seconds() > cfg.leg_max_minutes * 60:
                    break
    # remove duplicate/overlapping entries at same bar/direction
    out, seen = [], set()
    for s in sorted(signals, key=lambda z: (z["entry_idx"], z["direction"])):
        key = (s["entry_idx"], s["direction"])
        if key not in seen:
            seen.add(key); out.append(s)
    return out

def simulate_trade(df, sig, cfg):
    e = sig["entry_idx"]
    direction = sig["direction"]
    entry = float(df.at[e, "open"])
    activation = entry * (1 + direction * cfg.activation_pct / 100.0)
    deadline = df.at[e, "datetime"] + pd.Timedelta(minutes=cfg.max_trade_minutes)
    activated = False
    peak = entry
    stop = None

    for k in range(e, len(df)):
        ts = df.at[k, "datetime"]
        if ts > deadline:
            close = float(df.at[k-1, "close"])
            ret = direction * (close-entry) / entry * 100
            return _row(df, sig, e, k-1, entry, close, ret, "timeout", activated)

        hi, lo = float(df.at[k, "high"]), float(df.at[k, "low"])
        if direction == 1:
            if not activated and hi >= activation:
                activated = True
                peak = max(peak, hi)
                stop = peak * (1 - cfg.trail_pct/100)
            if activated:
                if hi > peak:
                    peak = hi
                    stop = peak * (1 - cfg.trail_pct/100)
                if lo <= stop:
                    close = stop
                    ret = (close-entry)/entry*100
                    return _row(df, sig, e, k, entry, close, ret, "trailing_stop", activated)
        else:
            if not activated and lo <= activation:
                activated = True
                peak = min(peak, lo)
                stop = peak * (1 + cfg.trail_pct/100)
            if activated:
                if lo < peak:
                    peak = lo
                    stop = peak * (1 + cfg.trail_pct/100)
                if hi >= stop:
                    close = stop
                    ret = (entry-close)/entry*100
                    return _row(df, sig, e, k, entry, close, ret, "trailing_stop", activated)
    close = float(df.iloc[-1]["close"])
    ret = direction * (close-entry)/entry*100
    return _row(df, sig, e, len(df)-1, entry, close, ret, "end_of_data", activated)

def _row(df, sig, e, x, entry, exit_price, ret, reason, activated):
    return {
        "entry_time": df.at[e,"datetime"],
        "exit_time": df.at[x,"datetime"],
        "direction": "Long" if sig["direction"]==1 else "Short",
        "entry": entry, "exit": exit_price,
        "return_pct": ret, "exit_reason": reason,
        "activated": activated,
        "pattern_end": sig["pattern_end"],
    }

def run_backtest(df, cfg):
    df = prepare(df)
    signals = find_signals(df, cfg)
    rows, bet = [], cfg.start_bet
    equity = 0.0
    peak_equity = 0.0
    max_dd = 0.0
    loss_streak = 0
    max_loss_streak = 0

    for sig in signals:
        tr = simulate_trade(df, sig, cfg)
        pnl = bet * tr["return_pct"] / 100.0
        tr["bet_eur"] = bet
        tr["pnl_eur"] = pnl
        equity += pnl
        peak_equity = max(peak_equity, equity)
        max_dd = max(max_dd, peak_equity-equity)
        if pnl > 0:
            loss_streak = 0
            if cfg.reset_on_profit:
                bet = cfg.start_bet
            else:
                bet = min(cfg.max_bet, bet * cfg.multiplier)
        else:
            loss_streak += 1
            max_loss_streak = max(max_loss_streak, loss_streak)
            bet = min(cfg.max_bet, bet * cfg.multiplier)
        tr["equity_eur"] = equity
        rows.append(tr)

    trades = pd.DataFrame(rows)
    stats = {
        "trades": len(trades),
        "net_profit_eur": float(trades["pnl_eur"].sum()) if len(trades) else 0.0,
        "win_rate_pct": float((trades["pnl_eur"] > 0).mean()*100) if len(trades) else 0.0,
        "max_bet_eur": float(trades["bet_eur"].max()) if len(trades) else 0.0,
        "max_loss_streak": int(max_loss_streak),
        "max_drawdown_eur": float(max_dd),
    }
    return trades, stats

def run_parameter_sweep(df, patterns, stops, base_cfg):
    results = []
    for p in patterns:
        for s in stops:
            cfg = BacktestConfig(**{**base_cfg.__dict__,
                "legs": int(p["legs"]), "move_pct": float(p["move_pct"]),
                "activation_pct": float(s["activation_pct"]),
                "trail_pct": float(s["trail_pct"])})
            trades, stats = run_backtest(df, cfg)
            results.append({
                "Muster": f'{p["legs"]}×{p["move_pct"]:.2f}%',
                "Aktivierung": f'{s["activation_pct"]:.2f}%',
                "Trailing": f'{s["trail_pct"]:.2f}%',
                **stats
            })
    return pd.DataFrame(results)
