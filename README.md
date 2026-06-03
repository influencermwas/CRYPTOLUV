# Market Signal Telegram Bot

Features:
- Telegram menu
- Crypto analysis from Binance public data
- Optional stock/forex analysis using Twelve Data API
- EMA, RSI, MACD, support/resistance, volume checks
- Entry, stop loss, take profit, confidence and reason
- Market news scanner and broadcast alerts
- Stores users in `users.json`

## Setup

1. Install Python 3.10+
2. Install requirements:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and add your Telegram bot token:

```bash
cp .env.example .env
```

4. Run:

```bash
python bot.py
```

## Commands

- `/start` - open menu
- `/analyze BTCUSDT` - analyze crypto
- `/analyze EUR/USD forex` - analyze forex if Twelve Data key is set
- `/analyze AAPL stock` - analyze stock if Twelve Data key is set
- `/news` - latest market news
- `/broadcast your message` - admin only

## Important warning
This bot gives analysis only. It cannot guarantee profit. Always use stop loss and risk management.
