# DAX Pattern + Martingale Backtest v4

v4 korrigiert die wichtigste Schwäche der vorherigen Version:
- Startbetrag wird als **maximales Risiko am Initial-Stop** interpretiert.
- Initial Stop ist immer aktiv.
- Nach Erreichen der Aktivierung übernimmt der Trailing Stop.
- Martingale verdoppelt das Risiko, nicht blind das Notional.
- Maximale Martingale-Stufe ist einstellbar.
- Muster und Stop-Sets sind frei testbar.
- Fortschrittsanzeige und CSV-Export.

Standard-DAX-CSV:
https://raw.githubusercontent.com/getdata-finance/ger30-1m-ohlcv-index-historical-data/main/GER30_1m.csv

Start:
pip install -r requirements.txt
streamlit run streamlit_app.py

Noch nicht enthalten: Spread, Slippage, Gebühren, Finanzierung und echte Intrabar-Tick-Reihenfolge.
