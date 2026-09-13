# DAX Pattern + Martingale Backtest v3

Verbesserte Streamlit-Version:
- schnellere NumPy-basierte Suche
- Fortschrittsbalken
- Datenumfang/Zeitraum sichtbar
- Muster frei einstellbar, z.B. 4×0,10 % oder 10×1 %
- Stop-Aktivierung und Trailing frei einstellbar
- automatischer Parameter-Sweep
- CSV-Export

Start:
`pip install -r requirements.txt`
`streamlit run streamlit_app.py`

Standard-CSV:
https://raw.githubusercontent.com/getdata-finance/ger30-1m-ohlcv-index-historical-data/main/GER30_1m.csv

Hinweis: P&L ist aktuell eine vereinfachte Notional-Modellierung. Reale Positionierung, Spread, Slippage, Gebühren und Finanzierung müssen für einen broker-nahen Test ergänzt werden.
