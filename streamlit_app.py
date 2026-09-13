
import streamlit as st
import pandas as pd
from backtest import BacktestConfig, run_backtest, run_parameter_sweep

st.set_page_config(page_title="Pattern + Martingale Backtest", layout="wide")
st.title("Pattern + Martingale Backtest")
st.caption("Flexible Muster, Trailing-Stops und automatischer Parametervergleich")

DEFAULT_URL = "https://raw.githubusercontent.com/getdata-finance/ger30-1m-ohlcv-index-historical-data/main/GER30_1m.csv"

with st.sidebar:
    st.header("Daten")
    upload = st.file_uploader("CSV hochladen", type=["csv"])
    url = st.text_input("Oder CSV-URL", DEFAULT_URL)

    st.header("Grundparameter")
    leg_max = st.number_input("Max. Minuten je Bewegung", 1, 1440, 15)
    pattern_max = st.number_input("Max. Minuten für gesamtes Muster", 1, 10000, 120)
    tolerance = st.number_input("Toleranz je Bewegung (%)", 0.0, 2.0, 0.01, 0.01)
    direction = st.selectbox("Richtung", ["both","long","short"])

    st.header("Martingale")
    start_bet = st.number_input("Startbetrag (€)", 0.01, 1000000.0, 10.0)
    max_bet = st.number_input("Max. Einsatz (€)", 0.01, 100000000.0, 100000.0)
    multiplier = st.number_input("Multiplikator nach Verlust", 1.0, 10.0, 2.0, 0.1)
    reset = st.checkbox("Nach Gewinn auf Startbetrag zurücksetzen", True)

    st.header("Trade-Dauer")
    max_trade = st.number_input("Max. Trade-Dauer (Minuten)", 1, 100000, 240)

    st.header("Einzeltest")
    move = st.number_input("Bewegung (%)", 0.01, 20.0, 0.10, 0.01)
    legs = st.number_input("Anzahl Bewegungen", 1, 100, 4)

base = BacktestConfig(
    move_pct=move, legs=int(legs), leg_max_minutes=int(leg_max),
    pattern_max_minutes=int(pattern_max), tolerance_pct=tolerance,
    max_trade_minutes=int(max_trade), start_bet=start_bet, max_bet=max_bet,
    multiplier=multiplier, reset_on_profit=reset, direction=direction
)

@st.cache_data
def load_csv(source, is_url):
    if is_url:
        return pd.read_csv(source)
    return pd.read_csv(source)

if upload is not None:
    df = load_csv(upload, False)
else:
    st.info("Standardmäßig wird die konfigurierbare DAX-1-Minuten-CSV-Quelle verwendet.")
    try:
        df = load_csv(url, True)
    except Exception as e:
        st.error(f"CSV konnte nicht geladen werden: {e}")
        st.stop()

tab1, tab2 = st.tabs(["Einzeltest", "Parameter-Sweep"])

with tab1:
    if st.button("Einzeltest starten", type="primary"):
        trades, stats = run_backtest(df, base)
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Trades", stats["trades"])
        c2.metric("Netto", f'{stats["net_profit_eur"]:.2f} €')
        c3.metric("Trefferquote", f'{stats["win_rate_pct"]:.1f} %')
        c4.metric("Max. Einsatz", f'{stats["max_bet_eur"]:.2f} €')
        c5.metric("Max. Drawdown", f'{stats["max_drawdown_eur"]:.2f} €')
        if len(trades):
            st.line_chart(trades.set_index("exit_time")["equity_eur"])
            st.dataframe(trades, use_container_width=True)
            st.download_button("Trades als CSV", trades.to_csv(index=False), "trades.csv")

with tab2:
    st.subheader("Viele Varianten automatisch testen")
    st.write("Beispiel: 4×0,10 %, 5×0,10 %, 10×0,10 %, 10×0,50 %, 10×1,00 %.")

    default_patterns = pd.DataFrame([
        {"legs":4,"move_pct":0.10},
        {"legs":5,"move_pct":0.10},
        {"legs":10,"move_pct":0.10},
        {"legs":10,"move_pct":0.50},
        {"legs":10,"move_pct":1.00},
    ])
    default_stops = pd.DataFrame([
        {"activation_pct":0.10,"trail_pct":0.05},
        {"activation_pct":0.10,"trail_pct":0.10},
        {"activation_pct":0.10,"trail_pct":0.20},
        {"activation_pct":0.20,"trail_pct":0.10},
        {"activation_pct":0.50,"trail_pct":0.20},
        {"activation_pct":1.00,"trail_pct":0.50},
    ])
    patterns = st.data_editor(default_patterns, num_rows="dynamic", use_container_width=True)
    stops = st.data_editor(default_stops, num_rows="dynamic", use_container_width=True)

    if st.button("Alle Varianten testen", type="primary"):
        result = run_parameter_sweep(df, patterns.to_dict("records"), stops.to_dict("records"), base)
        st.dataframe(result.sort_values("net_profit_eur", ascending=False), use_container_width=True)
        st.download_button("Sweep als CSV", result.to_csv(index=False), "parameter_sweep.csv")

st.warning(
    "Wichtig: OHLC-1-Minuten-Daten zeigen nicht die Reihenfolge von High/Low innerhalb einer Kerze. "
    "Für sehr enge Stops kann das Ergebnis deshalb vom tatsächlichen Tick-Verlauf abweichen. "
    "Spread, Slippage, Gebühren und Finanzierung sind noch nicht modelliert."
)
