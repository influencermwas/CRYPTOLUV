INFLUENCERTECH SIGNALS - ALL SYMBOL LIVE PRICE FIX

What changed:
1. All signals now refresh the current market price immediately before sending.
2. Crypto uses Binance live ticker first, then OKX fallback.
3. Forex, metals, stocks and indices use corrected Yahoo symbol mapping.
4. Gold/Silver use spot-style XAUUSD/XAGUSD mapping, not futures GC=F/SI=F.
5. The last candle close is synced to the live quote so Entry, TP and SL are calculated from the fresh market price.
6. Smart TP/SL now uses market structure + ATR buffer and has min/max caps so levels are not too far or too close.
7. Cache is reduced to 1 minute and live price still overrides cached candle close.

Important:
No public feed can be exactly the same as every MT5 broker because brokers have spread and liquidity-provider differences.
This update keeps the bot signal price close to the live reference market price and prevents stale/futures-mapped prices.

Render setup:
Build command: pip install -r requirements.txt
Start command: gunicorn app:app
After deploy open: https://cryptoluv.onrender.com/set_webhook
