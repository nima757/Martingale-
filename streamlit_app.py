import streamlit as st
import pandas as pd
from backtest import BacktestConfig,prepare,run_backtest,run_parameter_sweep

st.set_page_config(page_title="DAX Pattern + Martingale v4",layout="wide")
st.title("DAX Pattern + Martingale Backtest v4")
st.caption("Risiko-basiertes Martingale • echter Initial-Stop • Aktivierung + Trailing • Parameter-Sweep")
URL="https://raw.githubusercontent.com/getdata-finance/ger30-1m-ohlcv-index-historical-data/main/GER30_1m.csv"

@st.cache_data(show_spinner=False)
def load(x): return pd.read_csv(x)

with st.sidebar:
    st.header("Daten")
    up=st.file_uploader("CSV hochladen",type=["csv"])
    url=st.text_input("CSV-URL",URL)
    rows=st.number_input("Max. Zeilen (0=alle)",0,10000000,0,100000)
    st.header("Muster")
    move=st.number_input("Bewegung (%)",.01,20.,.10,.01)
    legs=st.number_input("Anzahl Bewegungen",1,100,4)
    legmax=st.number_input("Max. Minuten je Bewegung",1,1440,15)
    patmax=st.number_input("Max. Minuten gesamtes Muster",1,10000,120)
    tol=st.number_input("Toleranz (%)",0.,2.,.01,.01)
    direction=st.selectbox("Richtung",["both","long","short"],format_func=lambda x:{"both":"Long + Short","long":"Nur Long","short":"Nur Short"}[x])
    st.header("Stop / Risiko")
    init=st.number_input("Initial Stop (%)",.01,20.,.20,.01)
    act=st.number_input("Trailing-Aktivierung (%)",.01,20.,.10,.01)
    trail=st.number_input("Trailing-Abstand (%)",.01,20.,.10,.01)
    maxt=st.number_input("Max. Trade-Dauer (Min.)",1,100000,240)
    st.header("Martingale")
    risk=st.number_input("Start-Risiko (€)",.01,1000000.,10.,.01)
    maxrisk=st.number_input("Max. Risiko je Trade (€)",.01,100000000.,100000.,1.)
    mult=st.number_input("Multiplikator",1.,10.,2.,.1)
    maxstep=st.number_input("Max. Martingale-Stufe",0,30,7)
    reset=st.checkbox("Nach Gewinn zurücksetzen",True)

try:
    raw=load(up) if up is not None else load(url)
    if rows: raw=raw.tail(int(rows))
    df=prepare(raw)
except Exception as e:
    st.error(f"CSV konnte nicht geladen/erkannt werden: {e}");st.stop()

a,b,c=st.columns(3)
a.metric("Kerzen",f"{len(df):,}".replace(",","."));b.metric("Von",str(df.datetime.min()));c.metric("Bis",str(df.datetime.max()))

cfg=BacktestConfig(move_pct=move,legs=int(legs),leg_max_minutes=int(legmax),pattern_max_minutes=int(patmax),tolerance_pct=tol,
 initial_stop_pct=init,activation_pct=act,trail_pct=trail,max_trade_minutes=int(maxt),start_risk=risk,max_risk=maxrisk,
 multiplier=mult,max_martingale_steps=int(maxstep),reset_on_profit=reset,direction=direction)

t1,t2=st.tabs(["Einzeltest","Parameter-Sweep"])
with t1:
    st.info(f"Test: **{int(legs)}×{move:.2f}%** | Initial Stop **{init:.2f}%** | Aktivierung **{act:.2f}%** | Trailing **{trail:.2f}%** | Start-Risiko **{risk:.2f} €**")
    if st.button("▶ Einzeltest starten",type="primary",use_container_width=True):
        bar=st.progress(0,text="Mustersuche startet …")
        try:
            trades,stt=run_backtest(df,cfg,progress=lambda p:bar.progress(p,text=f"Berechnung: {p}%"))
            bar.progress(100,text="Fertig")
            st.success(f"Fertig — {stt['trades']} Trades.")
            cols=st.columns(6)
            for col,label,val in zip(cols,["Trades","Netto","Trefferquote","Max. Risiko","Max. Notional","Max. Drawdown"],
                [stt["trades"],f"{stt['net_profit_eur']:.2f} €",f"{stt['win_rate_pct']:.1f} %",
                 f"{stt['max_risk_eur']:.2f} €",f"{stt['max_notional_eur']:.0f} €",f"{stt['max_drawdown_eur']:.2f} €"]): col.metric(label,val)
            st.metric("Maximale Verlustserie",stt["max_loss_streak"])
            if len(trades):
                st.line_chart(trades.set_index("exit_time")["equity_eur"])
                st.dataframe(trades,use_container_width=True)
                st.download_button("Trades als CSV",trades.to_csv(index=False),"trades_v4.csv")
            else: st.warning("Keine passenden Muster gefunden.")
        except Exception as e: st.exception(e)

with t2:
    st.subheader("Automatischer Vergleich")
    patterns=st.data_editor(pd.DataFrame([{"legs":4,"move_pct":.10},{"legs":5,"move_pct":.10},{"legs":6,"move_pct":.10},
        {"legs":10,"move_pct":.10},{"legs":5,"move_pct":.50},{"legs":10,"move_pct":1.00}]),num_rows="dynamic",use_container_width=True)
    stops=st.data_editor(pd.DataFrame([{"initial_stop_pct":.10,"activation_pct":.10,"trail_pct":.05},
        {"initial_stop_pct":.20,"activation_pct":.10,"trail_pct":.10},{"initial_stop_pct":.30,"activation_pct":.10,"trail_pct":.10},
        {"initial_stop_pct":.50,"activation_pct":.20,"trail_pct":.10},{"initial_stop_pct":1.00,"activation_pct":.50,"trail_pct":.20}]),num_rows="dynamic",use_container_width=True)
    st.info(f"{len(patterns)} Muster × {len(stops)} Stop-Sets = **{len(patterns)*len(stops)} Tests**.")
    if st.button("▶ Alle Varianten testen",type="primary",use_container_width=True):
        bar=st.progress(0,text="Sweep startet …")
        try:
            r=run_parameter_sweep(df,patterns.to_dict("records"),stops.to_dict("records"),cfg,lambda p:bar.progress(p,text=f"Sweep: {p}%"))
            bar.progress(100,text="Sweep fertig")
            st.dataframe(r.sort_values("net_profit_eur",ascending=False),use_container_width=True)
            st.download_button("Sweep als CSV",r.to_csv(index=False),"sweep_v4.csv")
        except Exception as e: st.exception(e)

st.warning("Backtest-Hinweis: 1-Minuten-OHLC kann nicht zeigen, ob innerhalb derselben Kerze zuerst High oder Low erreicht wurde. "
"Spread, Slippage, Gebühren und Finanzierung sind noch nicht enthalten. Die Euro-Angabe ist jetzt ein maximales Risiko am Initial-Stop; daraus wird die Notionalgröße berechnet.")
