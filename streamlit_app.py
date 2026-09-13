import streamlit as st
import pandas as pd
from backtest import BacktestConfig, prepare, run_backtest, run_parameter_sweep

st.set_page_config(page_title="DAX Pattern + Martingale v3",layout="wide")
st.title("DAX Pattern + Martingale Backtest v3")
st.caption("Schnellere Suche • Fortschritt • frei einstellbare Muster und Stops")

DEFAULT_URL="https://raw.githubusercontent.com/getdata-finance/ger30-1m-ohlcv-index-historical-data/main/GER30_1m.csv"

@st.cache_data(show_spinner=False)
def load(source, uploaded):
    return pd.read_csv(source)

with st.sidebar:
    st.header("Daten")
    upload=st.file_uploader("CSV hochladen",type=["csv"])
    url=st.text_input("CSV-URL",DEFAULT_URL)
    max_rows=st.number_input("Max. Zeilen (0 = alle)",0,10000000,0,100000)
    st.header("Muster")
    move=st.number_input("Bewegung (%)",0.01,20.0,0.10,0.01)
    legs=st.number_input("Anzahl Bewegungen",1,100,4)
    leg_max=st.number_input("Max. Minuten je Bewegung",1,1440,15)
    pattern_max=st.number_input("Max. Minuten gesamtes Muster",1,10000,120)
    tolerance=st.number_input("Toleranz (%)",0.0,2.0,0.01,0.01)
    direction=st.selectbox("Richtung",["both","long","short"],format_func=lambda x:{"both":"Long + Short","long":"Nur Long","short":"Nur Short"}[x])
    st.header("Stop")
    activation=st.number_input("Aktivierung (%)",0.01,20.0,0.10,0.01)
    trail=st.number_input("Trailing-Abstand (%)",0.01,20.0,0.10,0.01)
    max_trade=st.number_input("Max. Trade-Dauer (Min.)",1,100000,240)
    st.header("Martingale")
    start=st.number_input("Startbetrag (€)",0.01,1000000.0,10.0)
    max_bet=st.number_input("Max. Einsatz (€)",0.01,100000000.0,100000.0)
    mult=st.number_input("Multiplikator",1.0,10.0,2.0,0.1)
    reset=st.checkbox("Nach Gewinn zurücksetzen",True)

try:
    raw=load(upload,True) if upload is not None else load(url,False)
    if max_rows: raw=raw.tail(int(max_rows))
    df=prepare(raw)
except Exception as e:
    st.error(f"CSV konnte nicht geladen/erkannt werden: {e}"); st.stop()

a,b,c=st.columns(3)
a.metric("Kerzen",f"{len(df):,}".replace(",",".")); b.metric("Von",str(df.datetime.min())); c.metric("Bis",str(df.datetime.max()))

cfg=BacktestConfig(move_pct=move,legs=int(legs),leg_max_minutes=int(leg_max),pattern_max_minutes=int(pattern_max),
                   tolerance_pct=tolerance,activation_pct=activation,trail_pct=trail,max_trade_minutes=int(max_trade),
                   start_bet=start,max_bet=max_bet,multiplier=mult,reset_on_profit=reset,direction=direction)

t1,t2=st.tabs(["Einzeltest","Parameter-Sweep"])
with t1:
    if st.button("▶ Einzeltest starten",type="primary",use_container_width=True):
        bar=st.progress(0,text="Mustersuche wird gestartet …")
        try:
            trades,stats=run_backtest(df,cfg,progress=lambda p:bar.progress(p,text=f"Berechnung: {p}%"))
            bar.progress(100,text="Fertig")
            st.success(f"Fertig — {stats['trades']} Trades gefunden.")
            x1,x2,x3,x4,x5=st.columns(5)
            x1.metric("Trades",stats["trades"]); x2.metric("Netto",f"{stats['net_profit_eur']:.2f} €")
            x3.metric("Trefferquote",f"{stats['win_rate_pct']:.1f} %"); x4.metric("Max. Einsatz",f"{stats['max_bet_eur']:.2f} €")
            x5.metric("Max. Drawdown",f"{stats['max_drawdown_eur']:.2f} €")
            if len(trades):
                st.line_chart(trades.set_index("exit_time")["equity_eur"])
                st.dataframe(trades,use_container_width=True)
                st.download_button("Trades als CSV",trades.to_csv(index=False),"trades.csv")
            else: st.warning("Keine passenden Muster gefunden.")
        except Exception as e: st.exception(e)

with t2:
    st.subheader("Alle Varianten automatisch testen")
    patterns=st.data_editor(pd.DataFrame([
        {"legs":4,"move_pct":0.10},{"legs":5,"move_pct":0.10},{"legs":10,"move_pct":0.10},
        {"legs":10,"move_pct":0.50},{"legs":10,"move_pct":1.00}]),num_rows="dynamic",use_container_width=True)
    stops=st.data_editor(pd.DataFrame([
        {"activation_pct":0.10,"trail_pct":0.05},{"activation_pct":0.10,"trail_pct":0.10},
        {"activation_pct":0.10,"trail_pct":0.20},{"activation_pct":0.20,"trail_pct":0.10},
        {"activation_pct":0.50,"trail_pct":0.20},{"activation_pct":1.00,"trail_pct":0.50}]),num_rows="dynamic",use_container_width=True)
    st.info(f"{len(patterns)} Muster × {len(stops)} Stops = {len(patterns)*len(stops)} Backtests")
    if st.button("▶ Alle Varianten testen",type="primary",use_container_width=True):
        bar=st.progress(0,text="Sweep startet …")
        try:
            r=run_parameter_sweep(df,patterns.to_dict("records"),stops.to_dict("records"),cfg,
                                  progress=lambda p:bar.progress(p,text=f"Sweep: {p}%"))
            bar.progress(100,text="Sweep fertig")
            st.dataframe(r.sort_values("net_profit_eur",ascending=False),use_container_width=True)
            st.download_button("Sweep als CSV",r.to_csv(index=False),"parameter_sweep.csv")
        except Exception as e: st.exception(e)

st.warning("OHLC-1-Minuten-Daten zeigen die Reihenfolge von High/Low innerhalb einer Kerze nicht. "
           "Enge Stops können daher abweichen. Spread, Slippage, Gebühren und Finanzierung sind noch nicht modelliert.")
