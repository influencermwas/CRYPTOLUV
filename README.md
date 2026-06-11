CRYPTO LUV BOT FIXES

1) MT5 link fixed per user
- /mt5link now creates a stable code: BRIDGE-USERID
- It no longer uses timestamp, so it will not change after restart/redeploy.
- IMPORTANT: Render free disk can reset JSON files after redeploy. This update still keeps the code stable even if mt5_users.json is lost.

2) Premium signal sending fixed
- Premium scan now sends a scanning message first.
- Scans crypto, forex, metals and stocks.
- Sends every found signal up to PREMIUM_DAILY_LIMIT.
- No more saying found 5 then only sending 2 because it no longer re-analyzes each signal before sending.

3) Premium grading fixed
- 79-84 confidence = B SIGNAL
- 85-89 confidence = A SIGNAL
- 90+ confidence = A+ SIGNAL

4) Metals included
- XAU/USD Gold
- XAG/USD Silver
- XPT/USD Platinum
- XPD/USD Palladium

Recommended Render ENV:
PUBLIC_URL=https://cryptoluv.onrender.com
PREMIUM_MIN_CONFIDENCE=79
A_SIGNAL_MIN_CONFIDENCE=85
A_PLUS_MIN_CONFIDENCE=90
PREMIUM_DAILY_LIMIT=5
PREMIUM_CRYPTO_SCAN_LIMIT=30
PREMIUM_FOREX_SCAN_LIMIT=24
PREMIUM_STOCK_SCAN_LIMIT=20
MAX_ACTIVE_MT5_ORDERS=4
