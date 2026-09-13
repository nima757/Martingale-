
# Pattern + Martingale Backtest (Streamlit)

Der Backtest testet wiederholte prozentuale Bewegungen und eine Martingale-Einsatzlogik.

## Frei einstellbar

### Muster
Beispiele:
- 4 × 0,10 %
- 5 × 0,10 %
- 10 × 0,10 %
- 10 × 0,50 %
- 10 × 1,00 %

### Stop
Beispiele:
- Aktivierung +0,10 %, Trailing 0,05 %
- Aktivierung +0,10 %, Trailing 0,10 %
- Aktivierung +0,20 %, Trailing 0,10 %
- Aktivierung +0,50 %, Trailing 0,20 %
- Aktivierung +1,00 %, Trailing 0,50 %

Der Parameter-Sweep testet alle Muster-Stop-Kombinationen automatisch.

## Start lokal

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## GitHub + Streamlit Community Cloud

Repository auf GitHub anlegen, Dateien hochladen und `streamlit_app.py` als App-Entrypoint auswählen.

## Wichtige Annahmen

- Ein Muster besteht aus gleichgerichteten Bewegungen der gewünschten Prozentgröße.
- Die nächste Kerze nach Abschluss des Musters ist der Einstieg.
- Der Trailing-Stop wird erst nach Erreichen des Aktivierungsziels aktiviert.
- Vor Aktivierung gibt es keinen festen Stop; alternativ kann dies später ergänzt werden.
- Martingale: Verlust -> Einsatz × Multiplikator; Gewinn -> optional zurück auf Startbetrag.
- Der Euro-Einsatz wird aktuell vereinfacht als Notional interpretiert: P&L = Einsatz × prozentuale Rendite.
- Keine Gebühren, Spreads, Slippage oder Finanzierung.
- OHLC-Daten können die intrabar Reihenfolge nicht vollständig rekonstruieren.

Für produktionsnahe Ergebnisse sollten Tickdaten bzw. sehr feine Daten und realistische Handelskosten verwendet werden.
