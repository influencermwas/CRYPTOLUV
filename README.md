# Market Signal Telegram Bot

Features:
- Telegram webhook bot for Render
- Crypto signals from Binance public candles
- Forex, stocks and metals via Twelve Data API
- Premium menu and admin activation
- Signal grades: B = 79–85%, A = 85–90%, A+ = 90%+
- Referral link and automatic +1 premium day when referred user activates premium
- TP/SL tracking endpoint for crypto signals
- Text broadcast and media/file/photo/video broadcast by copying a replied message

## Render setup

Build command:
```bash
pip install -r requirements.txt
```

Start command:
```bash
gunicorn app:app
```

Environment variables:
```bash
BOT_TOKEN=your telegram bot token
ADMIN_ID=your telegram user id
PUBLIC_URL=https://your-render-app.onrender.com
WEBHOOK_SECRET=make-a-secret-word
TWELVE_DATA_API_KEY=optional but needed for forex/stocks/metals
SIGNAL_CHANNEL_ID=-100xxxxxxxxxx
DEFAULT_PREMIUM_DAYS=30
```

After deploy, open:
```text
https://your-render-app.onrender.com/set_webhook
```

## Admin commands

Activate premium:
```text
/activate USER_ID DAYS
```

Text broadcast:
```text
/broadcast your message here
```

Media/file/photo/video broadcast:
1. Send the photo/video/file to the bot.
2. Reply to that message with:
```text
/copybroadcast
```

## Cron endpoints

Send automatic scan to SIGNAL_CHANNEL_ID:
```text
https://your-render-app.onrender.com/scan?secret=YOUR_SECRET&asset=crypto
https://your-render-app.onrender.com/scan?secret=YOUR_SECRET&asset=forex
https://your-render-app.onrender.com/scan?secret=YOUR_SECRET&asset=stock
```

Check TP/SL hits:
```text
https://your-render-app.onrender.com/check_tp?secret=YOUR_SECRET
```

Use UptimeRobot or cron-job.org every 5–15 minutes.

## Notes

This bot sends analysis signals only. It does not place trades. Use risk management.
