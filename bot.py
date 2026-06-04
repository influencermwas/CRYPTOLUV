import os
import json
import math
import logging

import requests
import pandas as pd
import feedparser
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "").strip()
NEWS_CHECK_MINUTES = int(os.getenv("NEWS_CHECK_MINUTES", "5") or 5)

USERS_FILE = "users.json"
NEWS_FILE = "seen_news.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

RISK_KEYWORDS = {
    "war": "Geopolitical risk",
    "attack": "Geopolitical risk",
    "missile": "Geopolitical risk",
    "invasion": "Geopolitical risk",
    "sanction": "Sanctions risk",
    "tariff": "Trade risk",
    "trade war": "Trade risk",
    "inflation": "Inflation risk",
    "interest rate": "Rate risk",
    "fed": "Central bank risk",
    "central bank": "Central bank risk",
    "recession": "Recession risk",
    "oil supply": "Oil risk",
    "crypto ban": "Crypto regulation risk",
    "hack": "Security risk",
    "exchange hack": "Crypto exchange risk",
    "etf approval": "Crypto ETF catalyst",
}

NEWS_FEEDS = [
    "https://news.google.com/rss/search?q=war+OR+sanctions+OR+tariff+OR+trade+war+markets&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=crypto+bitcoin+ethereum+hack+ban+ETF&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=forex+fed+inflation+interest+rates+dollar&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=stocks+nasdaq+sp500+earnings+inflation+fed&hl=en-US&gl=US&ceid=US:en",
]


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def register_user(user_id: int):
    users = load_json(USERS_FILE, [])
    if user_id not in users:
        users.append(user_id)
        save_json(USERS_FILE, users)


def main_menu():
    keyboard = [
        [InlineKeyboardButton("📈 Analyze Crypto", callback_data="crypto_help")],
        [InlineKeyboardButton("📊 Analyze Forex", callback_data="forex_help")],
        [InlineKeyboardButton("🏦 Analyze Stock", callback_data="stock_help")],
        [InlineKeyboardButton("📰 Market News", callback_data="news")],
        [InlineKeyboardButton("⚠️ Risk Rules", callback_data="risk")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user.id)

    text = (
        "🤖 *Market Signal Bot*\n\n"
        "I analyze crypto, forex and stocks using technical indicators and market news.\n\n"
        "Example commands:\n"
        "`/analyze BTCUSDT`\n"
        "`/analyze ETHUSDT`\n"
        "`/analyze SOLUSDT`\n"
        "`/analyze EUR/USD forex`\n"
        "`/analyze AAPL stock`\n\n"
        "⚠️ Signals are not guaranteed. Always use stop loss."
    )

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu())


async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    register_user(query.from_user.id)

    data = query.data

    if data == "crypto_help":
        await query.edit_message_text(
            "📈 Crypto examples:\n\n/analyze BTCUSDT\n/analyze ETHUSDT\n/analyze SOLUSDT",
            reply_markup=main_menu(),
        )
    elif data == "forex_help":
        await query.edit_message_text(
            "📊 Forex examples:\n\n/analyze EUR/USD forex\n/analyze XAU/USD forex\n\nRequires TWELVEDATA_API_KEY.",
            reply_markup=main_menu(),
        )
    elif data == "stock_help":
        await query.edit_message_text(
            "🏦 Stock examples:\n\n/analyze AAPL stock\n/analyze TSLA stock\n\nRequires TWELVEDATA_API_KEY.",
            reply_markup=main_menu(),
        )
    elif data == "news":
        await send_news_to_chat(query.message.chat_id, context)
    elif data == "risk":
        await query.edit_message_text(
            "⚠️ Risk rules:\n\n"
            "1. Never risk more than 1-2% per trade.\n"
            "2. Avoid trading during high-impact news.\n"
            "3. Always use stop loss.\n"
            "4. Wait for confirmation before entry.",
            reply_markup=main_menu(),
        )


def fetch_crypto_klines(symbol="BTCUSDT", interval="15", limit=150):
    symbol = symbol.upper().replace("/", "").replace("-", "")

    if symbol.endswith("USDT"):
        base = symbol.replace("USDT", "")
        inst_id = f"{base}-USDT"
    elif symbol.endswith("USD"):
        base = symbol.replace("USD", "")
        inst_id = f"{base}-USD"
    else:
        inst_id = symbol

    bar = "15m"
    if str(interval) in ["1", "3", "5", "15", "30"]:
        bar = f"{interval}m"
    elif str(interval) in ["60", "1h"]:
        bar = "1H"
    elif str(interval) in ["240", "4h"]:
        bar = "4H"
    elif str(interval) in ["1d", "D"]:
        bar = "1D"

    url = "https://www.okx.com/api/v5/market/candles"
    params = {"instId": inst_id, "bar": bar, "limit": str(limit)}
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.get(url, params=params, headers=headers, timeout=20)
    r.raise_for_status()

    data = r.json()
    if data.get("code") != "0":
        raise Exception(data.get("msg", "OKX API Error"))

    candles = data.get("data", [])
    if not candles:
        raise Exception(f"No candle data returned for {inst_id}")

    rows = []
    for c in reversed(candles):
        rows.append({
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": float(c[5]),
        })

    df = pd.DataFrame(rows)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col])

    return df


# Kept old name so app.py/older code does not break
def fetch_binance_klines(symbol="BTCUSDT", interval="15", limit=150):
    return fetch_crypto_klines(symbol, interval, limit)


def fetch_twelvedata(symbol: str, asset_type: str, interval="15min", outputsize=150):
    if not TWELVEDATA_API_KEY:
        raise ValueError("Twelve Data API key is missing. Add TWELVEDATA_API_KEY in Render Environment Variables.")

    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVEDATA_API_KEY,
    }

    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()

    data = r.json()
    if "values" not in data:
        raise ValueError(str(data))

    df = pd.DataFrame(data["values"])
    df = df.iloc[::-1].reset_index(drop=True)

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col])

    df["volume"] = pd.to_numeric(df.get("volume", 0), errors="coerce").fillna(0)
    return df


def add_indicators(df: pd.DataFrame):
    df = df.copy()
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, math.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    return df


def generate_signal(df: pd.DataFrame, symbol: str):
    df = add_indicators(df)
    last = df.iloc[-1]

    close = float(last["close"])
    support = float(df["low"].tail(30).min())
    resistance = float(df["high"].tail(30).max())

    avg_volume = float(df["volume"].tail(30).mean()) if df["volume"].sum() > 0 else 0
    volume_ok = avg_volume == 0 or float(last["volume"]) >= avg_volume * 0.8

    bullish = 0
    bearish = 0
    reasons = []

    if last["ema20"] > last["ema50"]:
        bullish += 1
        reasons.append("EMA20 is above EMA50")
    else:
        bearish += 1
        reasons.append("EMA20 is below EMA50")

    if close > last["ema200"]:
        bullish += 1
        reasons.append("Price is above EMA200")
    else:
        bearish += 1
        reasons.append("Price is below EMA200")

    if 45 <= last["rsi"] <= 68:
        bullish += 1
        reasons.append(f"RSI is healthy at {last['rsi']:.1f}")
    elif last["rsi"] > 72:
        bearish += 1
        reasons.append(f"RSI is overbought at {last['rsi']:.1f}")
    elif last["rsi"] < 35:
        bullish += 1
        reasons.append(f"RSI is oversold at {last['rsi']:.1f}")
    else:
        reasons.append(f"RSI is neutral at {last['rsi']:.1f}")

    if last["macd"] > last["macd_signal"]:
        bullish += 1
        reasons.append("MACD is bullish")
    else:
        bearish += 1
        reasons.append("MACD is bearish")

    if volume_ok:
        bullish += 1
        reasons.append("Volume is acceptable")
    else:
        bearish += 1
        reasons.append("Volume is weak")

    if bullish > bearish:
        direction = "BUY / LONG"
        entry_low = close * 0.998
        entry_high = close * 1.002
        stop = min(support, close * 0.985)
        tp1 = close * 1.015
        tp2 = close * 1.030
    elif bearish > bullish:
        direction = "SELL / SHORT"
        entry_low = close * 0.998
        entry_high = close * 1.002
        stop = max(resistance, close * 1.015)
        tp1 = close * 0.985
        tp2 = close * 0.970
    else:
        direction = "WAIT"
        entry_low = close
        entry_high = close
        stop = support
        tp1 = resistance
        tp2 = resistance

    confidence = min(90, max(45, 50 + abs(bullish - bearish) * 10))
    risk = "Low" if confidence >= 75 else "Medium" if confidence >= 60 else "High"

    return (
        f"📊 *{symbol.upper()} Signal*\n\n"
        f"Direction: *{direction}*\n"
        f"Current Price: `{close:.6g}`\n"
        f"Entry Zone: `{entry_low:.6g} - {entry_high:.6g}`\n"
        f"Stop Loss: `{stop:.6g}`\n"
        f"Take Profit 1: `{tp1:.6g}`\n"
        f"Take Profit 2: `{tp2:.6g}`\n\n"
        f"Support: `{support:.6g}`\n"
        f"Resistance: `{resistance:.6g}`\n"
        f"Risk: *{risk}*\n"
        f"Confidence: *{confidence}%*\n\n"
        "Reason:\n- " + "\n- ".join(reasons) +
        "\n\n⚠️ This is analysis only, not guaranteed profit."
    )


async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user.id)

    if not context.args:
        await update.message.reply_text(
            "Use:\n"
            "/analyze BTCUSDT\n"
            "/analyze ETHUSDT\n"
            "/analyze SOLUSDT\n"
            "/analyze EUR/USD forex\n"
            "/analyze AAPL stock"
        )
        return

    symbol = context.args[0].upper()
    asset_type = context.args[1].lower() if len(context.args) > 1 else "crypto"

    try:
        if asset_type == "crypto":
            df = fetch_crypto_klines(symbol, "15", 150)
        elif asset_type in ["forex", "stock"]:
            df = fetch_twelvedata(symbol, asset_type)
        else:
            await update.message.reply_text("Asset type must be crypto, forex, or stock.")
            return

        signal = generate_signal(df, symbol)
        await update.message.reply_text(signal, parse_mode="Markdown")
    except Exception as e:
        logger.exception("Analyze error")
        await update.message.reply_text(f"❌ Could not analyze {symbol}. Error: {e}")


def scan_news():
    results = []
    seen = load_json(NEWS_FILE, [])
    seen_set = set(seen)

    for feed_url in NEWS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:5]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            key = link or title

            if not key or key in seen_set:
                continue

            lowered = title.lower()
            matched = []
            for word, reason in RISK_KEYWORDS.items():
                if word in lowered:
                    matched.append(reason)

            if matched:
                results.append({
                    "title": title,
                    "link": link,
                    "reason": sorted(set(matched)),
                })
                seen.append(key)

    save_json(NEWS_FILE, seen[-500:])
    return results


def format_news_alert(item):
    reasons = ", ".join(item["reason"])
    return (
        "🚨 *MARKET NEWS ALERT*\n\n"
        f"Impact: *High Risk*\n"
        f"Topic: {reasons}\n\n"
        f"Headline: {item['title']}\n\n"
        "Advice: Avoid blind entries. Wait for confirmation and reduce lot size.\n"
        f"Source: {item['link']}"
    )


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user.id)
    await send_news_to_chat(update.effective_chat.id, context)


async def send_news_to_chat(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    items = scan_news()

    if not items:
        await context.bot.send_message(chat_id=chat_id, text="📰 No new high-risk market news detected right now.")
        return

    for item in items[:5]:
        await context.bot.send_message(chat_id=chat_id, text=format_news_alert(item), parse_mode="Markdown")


async def scheduled_news_check(context: ContextTypes.DEFAULT_TYPE):
    items = scan_news()
    if not items:
        return

    users = load_json(USERS_FILE, [])
    for user_id in users:
        for item in items[:3]:
            try:
                await context.bot.send_message(chat_id=user_id, text=format_news_alert(item), parse_mode="Markdown")
            except Exception as e:
                logger.warning("Failed to send news to %s: %s", user_id, e)


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only.")
        return

    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("Use: /broadcast your message")
        return

    users = load_json(USERS_FILE, [])
    sent = 0
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 *Broadcast*\n\n{message}", parse_mode="Markdown")
            sent += 1
        except Exception:
            pass

    await update.message.reply_text(f"✅ Broadcast sent to {sent} users.")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN missing. Add it in .env or Render Environment Variables.")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analyze", analyze))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(button_click))

    app.job_queue.run_repeating(scheduled_news_check, interval=NEWS_CHECK_MINUTES * 60, first=20)

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
