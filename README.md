# CRYPTO LUV Updated Telegram Signal Bot

This package is Render-ready and keeps the restored bot updates:

- Premium button and premium signals
- Referral links and 1-day premium reward after invited user activates premium
- Crypto, forex, stocks and metals scanning
- Gold XAU/USD, Silver XAG/USD, Platinum XPT/USD, Palladium XPD/USD
- Signal grading:
  - 79-84% = B SIGNAL
  - 85-89% = A SIGNAL
  - 90%+ = A+ SIGNAL
- VIP history and performance
- TP/SL tracking/maintenance endpoint
- Admin broadcast
- Admin stats
- MT5 bridge endpoints
- M-Pesa callback route
- Python pinned to 3.11 to avoid pandas build failure on Render Python 3.14

## Render setup

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
gunicorn app:app
```

Add environment variables from `.env.example`.

Important:

```text
PUBLIC_URL=https://cryptoluv.onrender.com
```

After deploy, open:

```text
https://cryptoluv.onrender.com/set_webhook
```

Check webhook:

```text
https://cryptoluv.onrender.com/webhook_info
```

Cron URL for news and VIP maintenance:

```text
https://cryptoluv.onrender.com/check_news?secret=YOUR_CRON_SECRET
```

Set this cron every 5 minutes using UptimeRobot or cron-job.org.
