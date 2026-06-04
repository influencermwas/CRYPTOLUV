import os
import json
import math
import base64
import logging
from datetime import datetime, timedelta, timezone

import requests
import pandas as pd
import feedparser
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "").strip()
NEWS_CHECK_MINUTES = int(os.getenv("NEWS_CHECK_MINUTES", "5") or 5)

PREMIUM_PRICE = int(os.getenv("PREMIUM_PRICE", "35") or 35)

MPESA_ENV = os.getenv("MPESA_ENV", "sandbox").strip().lower()  # sandbox or live
MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY", "").strip()
MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET", "").strip()
MPESA_SHORTCODE = os.getenv("MPESA_SHORTCODE", "").strip()
MPESA_PASSKEY = os.getenv("MPESA_PASSKEY", "").strip()
MPESA_CALLBACK_URL = os.getenv("MPESA_CALLBACK_URL", "").strip()
MPESA_TRANSACTION_TYPE = os.getenv("MPESA_TRANSACTION_TYPE", "CustomerPayBillOnline").strip()

USERS_FILE = "users.json"
NEWS_FILE = "seen_news.json"
PREMIUM_FILE = "premium_users.json"
PENDING_FILE = "pending_payments.json"

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

FREE_CONFIDENCE_LIMIT = int(os.getenv("FREE_CONFIDENCE_LIMIT", "80") or 80)
PREMIUM_MIN_CONFIDENCE = int(os.getenv("PREMIUM_MIN_CONFIDENCE", "80") or 80)
PREMIUM_DAILY_LIMIT = int(os.getenv("PREMIUM_DAILY_LIMIT", "5") or 5)

REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@influencertechgc").strip()
DATA_BOT_URL = os.getenv("DATA_BOT_URL", "https://t.me/INFLUENCERTECHHUB_BOT?start=5352491388").strip()

CRYPTO_WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "WLDUSDT", "CELOUSDT", "AVAXUSDT", "LINKUSDT", "TONUSDT",
    "DOTUSDT", "NEARUSDT", "OPUSDT", "ARBUSDT", "APTUSDT", "INJUSDT",
    "SUIUSDT", "TRXUSDT", "LTCUSDT", "BCHUSDT", "PEPEUSDT", "SHIBUSDT",
]

FOREX_WATCHLIST = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CAD", "AUD/USD", "NZD/USD",
    "USD/CHF", "GBP/JPY", "EUR/JPY", "XAU/USD",
]

STOCK_WATCHLIST = [
    "AAPL", "TSLA", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "AMD", "NFLX",
]


def now_utc():
    return datetime.now(timezone.utc)


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


def is_premium(user_id: int):
    premium = load_json(PREMIUM_FILE, {})
    expires = premium.get(str(user_id))
    if not expires:
        return False, None
    try:
        expires_dt = datetime.fromisoformat(expires)
        if expires_dt > now_utc():
            return True, expires_dt
    except Exception:
        pass
    return False, None


def activate_premium(user_id: int, hours=24):
    premium = load_json(PREMIUM_FILE, {})
    expires_dt = now_utc() + timedelta(hours=hours)
    premium[str(user_id)] = expires_dt.isoformat()
    save_json(PREMIUM_FILE, premium)
    return expires_dt



def gate_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Start Data Bot", url=DATA_BOT_URL)],
        [InlineKeyboardButton("📢 Join Main Channel", url="https://t.me/influencertechgc")],
        [InlineKeyboardButton("✅ I Have Done It", callback_data="verify_access")],
    ])


async def has_required_access(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """
    Telegram can verify channel membership.
    Telegram cannot verify that a user started another bot unless both bots share a database.
    So this gate shows the data bot link and verifies the channel.
    """
    if not REQUIRED_CHANNEL:
        return True

    try:
        member = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.warning("Access check failed for %s: %s", user_id, e)
        return False


async def send_access_gate(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "🔒 *Access Locked*\n\n"
            "Before using INFLUENCERTECH SIGNALS, complete these steps:\n\n"
            "1️⃣ Start our data bot\n"
            "2️⃣ Join our main channel\n\n"
            "After that, tap ✅ *I Have Done It*."
        ),
        parse_mode="Markdown",
        reply_markup=gate_keyboard(),
    )


def main_menu():
    keyboard = [
        [
            InlineKeyboardButton("⚡ BTC", callback_data="quick_BTCUSDT"),
            InlineKeyboardButton("⚡ ETH", callback_data="quick_ETHUSDT"),
            InlineKeyboardButton("⚡ SOL", callback_data="quick_SOLUSDT"),
        ],
        [
            InlineKeyboardButton("⚡ XRP", callback_data="quick_XRPUSDT"),
            InlineKeyboardButton("⚡ BNB", callback_data="quick_BNBUSDT"),
            InlineKeyboardButton("⚡ DOGE", callback_data="quick_DOGEUSDT"),
        ],
        [InlineKeyboardButton("💎 Premium Signals", callback_data="premium")],
        [InlineKeyboardButton("📰 Market News", callback_data="news")],
        [InlineKeyboardButton("⚠️ Risk Rules", callback_data="risk")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user.id)

    if not await has_required_access(update.effective_user.id, context):
        await send_access_gate(update.effective_chat.id, context)
        return

    active, expires = is_premium(update.effective_user.id)
    premium_text = f"✅ Premium active until `{expires.strftime('%Y-%m-%d %H:%M UTC')}`" if active else "🔒 Premium locked"

    text = (
        "🔥 *INFLUENCERTECH SIGNALS* 🔥\n\n"
        "Send a symbol directly, example:\n"
        "`BTCUSDT`, `ETHUSDT`, `SOLUSDT`\n\n"
        "Or tap quick analysis buttons below.\n\n"
        f"{premium_text}\n\n"
        "Premium is KSh 35 for 24 hours.\n"
        "⚠️ Signals are not guaranteed. Always use stop loss."
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu())


async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    register_user(query.from_user.id)
    data = query.data

    if data == "verify_access":
        if await has_required_access(query.from_user.id, context):
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="✅ Access verified. Welcome to INFLUENCERTECH SIGNALS.",
                reply_markup=main_menu(),
            )
        else:
            await send_access_gate(query.message.chat_id, context)
        return

    if not await has_required_access(query.from_user.id, context):
        await send_access_gate(query.message.chat_id, context)
        return

    if data.startswith("quick_"):
        symbol = data.replace("quick_", "")
        await send_analysis(query.message.chat_id, query.from_user.id, context, symbol, "crypto", premium=False)
    elif data == "premium":
        await show_premium(query.message.chat_id, query.from_user.id, context)
    elif data == "vip_signal":
        await premium_signals(query.message.chat_id, query.from_user.id, context)
    elif data == "pay_premium":
        context.user_data["awaiting_premium_phone"] = True
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(
                "💎 *Premium Subscription*\n\n"
                f"Price: *KSh {PREMIUM_PRICE}*\n"
                "Duration: *24 hours*\n\n"
                "Send your M-Pesa number now.\n"
                "Example: `0712345678`"
            ),
            parse_mode="Markdown",
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


async def show_premium(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    active, expires = is_premium(user_id)
    if active:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Get 5 VIP Signals", callback_data="vip_signal")]])
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "✅ *Premium Active*\n\n"
                f"Expires: `{expires.strftime('%Y-%m-%d %H:%M UTC')}`\n\n"
                "Tap below to receive today's VIP signals."
            ),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        return

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💳 Pay KSh 35 via M-Pesa", callback_data="pay_premium")]])
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "💎 *INFLUENCERTECH VIP SIGNALS*\n\n"
            f"Price: *KSh {PREMIUM_PRICE}*\n"
            "Access: *24 hours*\n\n"
            "Includes:\n"
            "🔥 VIP entries\n"
            "🔥 TP1 / TP2 / TP3\n"
            "🔥 Stop loss\n"
            "🔥 CHoCH, BOS, FVG\n"
            "🔥 Order block and liquidity sweep\n\n"
            "Tap below to pay automatically using STK Push."
        ),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


def normalize_phone(phone: str):
    phone = "".join(ch for ch in phone if ch.isdigit())
    if phone.startswith("0") and len(phone) == 10:
        return "254" + phone[1:]
    if phone.startswith("254") and len(phone) == 12:
        return phone
    if phone.startswith("7") and len(phone) == 9:
        return "254" + phone
    raise ValueError("Invalid phone number. Use format 0712345678 or 254712345678.")


def mpesa_base_url():
    if MPESA_ENV == "live":
        return "https://api.safaricom.co.ke"
    return "https://sandbox.safaricom.co.ke"


def get_mpesa_token():
    if not MPESA_CONSUMER_KEY or not MPESA_CONSUMER_SECRET:
        raise ValueError("M-Pesa consumer key/secret missing.")

    url = f"{mpesa_base_url()}/oauth/v1/generate?grant_type=client_credentials"
    r = requests.get(url, auth=(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET), timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


def send_stk_push(user_id: int, phone: str):
    if not MPESA_SHORTCODE or not MPESA_PASSKEY or not MPESA_CALLBACK_URL:
        raise ValueError("M-Pesa shortcode/passkey/callback URL missing in Render Environment Variables.")

    access_token = get_mpesa_token()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password_raw = f"{MPESA_SHORTCODE}{MPESA_PASSKEY}{timestamp}"
    password = base64.b64encode(password_raw.encode()).decode()

    url = f"{mpesa_base_url()}/mpesa/stkpush/v1/processrequest"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    payload = {
        "BusinessShortCode": MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": MPESA_TRANSACTION_TYPE,
        "Amount": PREMIUM_PRICE,
        "PartyA": phone,
        "PartyB": MPESA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": MPESA_CALLBACK_URL,
        "AccountReference": f"VIP{user_id}",
        "TransactionDesc": "InfluencerTech VIP Signals",
    }

    r = requests.post(url, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()

    if data.get("ResponseCode") != "0":
        raise Exception(data.get("errorMessage") or data.get("ResponseDescription") or str(data))

    checkout_id = data.get("CheckoutRequestID")
    pending = load_json(PENDING_FILE, {})
    pending[checkout_id] = {
        "user_id": user_id,
        "phone": phone,
        "amount": PREMIUM_PRICE,
        "created_at": now_utc().isoformat(),
    }
    save_json(PENDING_FILE, pending)
    return data


async def handle_premium_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    raw_phone = update.message.text.strip()

    try:
        phone = normalize_phone(raw_phone)
        await update.message.reply_text("📲 Sending M-Pesa STK Push. Check your phone and enter PIN...")

        data = send_stk_push(user_id, phone)
        checkout_id = data.get("CheckoutRequestID", "pending")

        await update.message.reply_text(
            "✅ STK Push sent.\n\n"
            f"Amount: KSh {PREMIUM_PRICE}\n"
            f"Phone: {phone}\n\n"
            "After payment, premium will open automatically for 24 hours."
        )
        context.user_data["awaiting_premium_phone"] = False
        logger.info("STK sent to %s for user %s checkout %s", phone, user_id, checkout_id)

    except Exception as e:
        logger.exception("Premium payment error")
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Payment request failed: {e}")


async def handle_mpesa_callback(data: dict, bot):
    callback = data.get("Body", {}).get("stkCallback", {})
    result_code = callback.get("ResultCode")
    result_desc = callback.get("ResultDesc", "")
    checkout_id = callback.get("CheckoutRequestID")

    pending = load_json(PENDING_FILE, {})
    payment = pending.get(checkout_id)

    if not payment:
        logger.warning("Unknown checkout callback: %s", checkout_id)
        return {"ok": True, "message": "Unknown checkout ignored"}

    user_id = int(payment["user_id"])

    if result_code == 0:
        expires = activate_premium(user_id, 24)
        pending.pop(checkout_id, None)
        save_json(PENDING_FILE, pending)

        await bot.send_message(
            chat_id=user_id,
            text=(
                "✅ *Payment received!*\n\n"
                "💎 Premium Signals activated for *24 hours*.\n"
                f"Expires: `{expires.strftime('%Y-%m-%d %H:%M UTC')}`\n\n"
                "Tap /start then 💎 Premium Signals."
            ),
            parse_mode="Markdown",
        )
        return {"ok": True, "message": "Premium activated"}

    pending.pop(checkout_id, None)
    save_json(PENDING_FILE, pending)

    await bot.send_message(
        chat_id=user_id,
        text=(
            "❌ *Payment not completed.*\n\n"
            f"Reason: {result_desc}\n\n"
            "Premium remains locked. You can try again from 💎 Premium Signals."
        ),
        parse_mode="Markdown",
    )
    return {"ok": True, "message": "Payment failed/rejected"}


def to_okx_symbol(symbol: str):
    symbol = symbol.upper().replace("/", "").replace("-", "")
    if symbol.endswith("USDT"):
        base = symbol.replace("USDT", "")
        return f"{base}-USDT"
    if symbol.endswith("USD"):
        base = symbol.replace("USD", "")
        return f"{base}-USD"
    return symbol


def interval_to_okx_bar(interval):
    interval = str(interval).lower()
    if interval in ["1", "3", "5", "15", "30"]:
        return f"{interval}m"
    if interval in ["60", "1h"]:
        return "1H"
    if interval in ["240", "4h"]:
        return "4H"
    if interval in ["1d", "d"]:
        return "1D"
    return "15m"


def fetch_crypto_klines(symbol="BTCUSDT", interval="15", limit=150):
    inst_id = to_okx_symbol(symbol)
    bar = interval_to_okx_bar(interval)

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


def simple_trend(df: pd.DataFrame):
    df = add_indicators(df)
    last = df.iloc[-1]
    if last["ema20"] > last["ema50"] and last["close"] > last["ema200"]:
        return "Bullish"
    if last["ema20"] < last["ema50"] and last["close"] < last["ema200"]:
        return "Bearish"
    return "Mixed"


def detect_liquidity_sweep(df: pd.DataFrame):
    recent = df.tail(25)
    last = df.iloc[-1]
    previous_high = recent["high"].iloc[:-1].max()
    previous_low = recent["low"].iloc[:-1].min()

    if last["high"] > previous_high and last["close"] < previous_high:
        return "Buy-side liquidity sweep detected"
    if last["low"] < previous_low and last["close"] > previous_low:
        return "Sell-side liquidity sweep detected"
    return "No clear liquidity sweep"


def detect_bos_choch(df: pd.DataFrame):
    recent = df.tail(40).reset_index(drop=True)
    last_close = recent["close"].iloc[-1]

    prior_high = recent["high"].iloc[-20:-1].max()
    prior_low = recent["low"].iloc[-20:-1].min()
    older_high = recent["high"].iloc[-40:-20].max()
    older_low = recent["low"].iloc[-40:-20].min()

    structure_before = "Bullish" if prior_high > older_high and prior_low > older_low else "Bearish" if prior_high < older_high and prior_low < older_low else "Range"

    if last_close > prior_high:
        if structure_before == "Bearish":
            return "Bullish CHoCH detected", "Bullish"
        return "Bullish BOS detected", "Bullish"

    if last_close < prior_low:
        if structure_before == "Bullish":
            return "Bearish CHoCH detected", "Bearish"
        return "Bearish BOS detected", "Bearish"

    return "No fresh BOS/CHoCH", "Neutral"


def detect_fvg(df: pd.DataFrame):
    recent = df.tail(30).reset_index(drop=True)
    last_fvg = None

    for i in range(2, len(recent)):
        c1 = recent.iloc[i - 2]
        c3 = recent.iloc[i]

        if c3["low"] > c1["high"]:
            last_fvg = ("Bullish FVG", float(c1["high"]), float(c3["low"]))

        if c3["high"] < c1["low"]:
            last_fvg = ("Bearish FVG", float(c3["high"]), float(c1["low"]))

    if not last_fvg:
        return "No clear FVG"

    fvg_type, low_zone, high_zone = last_fvg
    return f"{fvg_type}: {low_zone:.6g} - {high_zone:.6g}"


def detect_order_block(df: pd.DataFrame):
    recent = df.tail(35).reset_index(drop=True)
    last_close = recent["close"].iloc[-1]
    prior_high = recent["high"].iloc[-20:-1].max()
    prior_low = recent["low"].iloc[-20:-1].min()

    if last_close > prior_high:
        bearish_candles = recent[(recent["close"] < recent["open"])].tail(3)
        if not bearish_candles.empty:
            ob = bearish_candles.iloc[-1]
            return f"Bullish OB zone: {float(ob['low']):.6g} - {float(ob['high']):.6g}"

    if last_close < prior_low:
        bullish_candles = recent[(recent["close"] > recent["open"])].tail(3)
        if not bullish_candles.empty:
            ob = bullish_candles.iloc[-1]
            return f"Bearish OB zone: {float(ob['low']):.6g} - {float(ob['high']):.6g}"

    return "No clear order block"


def generate_signal(df: pd.DataFrame, symbol: str, mtf=None, vip=False, lock_free=True, return_meta=False):
    df = add_indicators(df)
    last = df.iloc[-1]

    close = float(last["close"])
    support = float(df["low"].tail(30).min())
    resistance = float(df["high"].tail(30).max())

    avg_volume = float(df["volume"].tail(30).mean()) if df["volume"].sum() > 0 else 0
    volume_ok = avg_volume == 0 or float(last["volume"]) >= avg_volume * 0.8

    liquidity = detect_liquidity_sweep(df)
    structure_text, structure_bias = detect_bos_choch(df)
    fvg = detect_fvg(df)
    order_block = detect_order_block(df)

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

    if structure_bias == "Bullish":
        bullish += 2
        reasons.append(structure_text)
    elif structure_bias == "Bearish":
        bearish += 2
        reasons.append(structure_text)
    else:
        reasons.append(structure_text)

    if "Bullish FVG" in fvg:
        bullish += 1
        reasons.append(fvg)
    elif "Bearish FVG" in fvg:
        bearish += 1
        reasons.append(fvg)
    else:
        reasons.append(fvg)

    if "Sell-side liquidity sweep" in liquidity:
        bullish += 1
        reasons.append(liquidity)
    elif "Buy-side liquidity sweep" in liquidity:
        bearish += 1
        reasons.append(liquidity)
    else:
        reasons.append(liquidity)

    if mtf:
        mtf_bullish = sum(1 for x in mtf.values() if x == "Bullish")
        mtf_bearish = sum(1 for x in mtf.values() if x == "Bearish")

        if mtf_bullish >= 2:
            bullish += 2
            reasons.append("Multi-timeframe trend supports bullish setup")
        elif mtf_bearish >= 2:
            bearish += 2
            reasons.append("Multi-timeframe trend supports bearish setup")
        else:
            reasons.append("Multi-timeframe trend is mixed")

    if bullish > bearish:
        direction = "BUY / LONG"
        rating = "🟢 STRONG BUY" if bullish - bearish >= 4 else "🟡 BUY"
        entry_low = close * 0.998
        entry_high = close * 1.002
        stop = min(support, close * 0.985)
        tp1 = close * 1.015
        tp2 = close * 1.030
        tp3 = close * 1.050
    elif bearish > bullish:
        direction = "SELL / SHORT"
        rating = "🔴 STRONG SELL" if bearish - bullish >= 4 else "🟠 SELL"
        entry_low = close * 0.998
        entry_high = close * 1.002
        stop = max(resistance, close * 1.015)
        tp1 = close * 0.985
        tp2 = close * 0.970
        tp3 = close * 0.950
    else:
        direction = "WAIT"
        rating = "⚪ NEUTRAL"
        entry_low = close
        entry_high = close
        stop = support
        tp1 = resistance
        tp2 = resistance
        tp3 = resistance

    confidence = min(92, max(45, 50 + abs(bullish - bearish) * 7))
    risk = "Low" if confidence >= 78 else "Medium" if confidence >= 62 else "High"
    mtf_text = "Not available"
    if mtf:
        mtf_text = " | ".join([f"{tf}: {trend}" for tf, trend in mtf.items()])

    vip_header = "💎 *VIP PREMIUM SIGNAL*\n" if vip else ""

    if return_meta:
        return {
            "symbol": symbol.upper(),
            "confidence": confidence,
            "rating": rating,
            "direction": direction,
            "risk": risk,
        }

    if lock_free and not vip and confidence >= FREE_CONFIDENCE_LIMIT:
        free_confidence = min(79, confidence)
        return (
            f"📊 *{symbol.upper()} Free Scalp Signal*\n"
            f"🔥 *INFLUENCERTECH SIGNALS* 🔥\n\n"
            f"Rating: *{rating}*\n"
            f"Direction: *{direction}*\n"
            f"Current Price: `{close:.6g}`\n"
            f"Entry Zone: `{entry_low:.6g} - {entry_high:.6g}`\n"
            f"Stop Loss: `{stop:.6g}`\n"
            f"Take Profit 1: `{tp1:.6g}`\n"
            f"Take Profit 2: `{tp2:.6g}`\n"
            f"Risk: *{risk}*\n"
            f"Free Confidence: *{free_confidence}%*\n\n"
            "📌 *Free Analysis*\n"
            f"Support: `{support:.6g}`\n"
            f"Resistance: `{resistance:.6g}`\n"
            "SMC details are locked for premium.\n\n"
            "🔒 *Premium Unlocks:*\n"
            "- Full confidence score\n"
            "- CHoCH/BOS confirmation\n"
            "- FVG zone\n"
            "- Order block\n"
            "- Liquidity sweep\n"
            "- Multi-timeframe trend\n"
            "- TP3 and risk-reward ratio\n\n"
            f"💎 Subscribe for *KSh {PREMIUM_PRICE}* to unlock VIP signals for 24 hours.\n"
            "Tap /start then choose 💎 Premium Signals."
        )

    extra_vip = ""
    if vip:
        extra_vip = (
            f"Take Profit 3: `{tp3:.6g}`\n"
            f"Risk Reward: `Approx 1:{abs((tp2-close)/(close-stop)):.2f}`\n\n"
        )

    return (
        f"{vip_header}"
        f"📊 *{symbol.upper()} Signal*\n"
        f"🔥 *INFLUENCERTECH SIGNALS* 🔥\n\n"
        f"Rating: *{rating}*\n"
        f"Direction: *{direction}*\n"
        f"Current Price: `{close:.6g}`\n"
        f"Entry Zone: `{entry_low:.6g} - {entry_high:.6g}`\n"
        f"Stop Loss: `{stop:.6g}`\n"
        f"Take Profit 1: `{tp1:.6g}`\n"
        f"Take Profit 2: `{tp2:.6g}`\n"
        f"{extra_vip}"
        f"Support: `{support:.6g}`\n"
        f"Resistance: `{resistance:.6g}`\n"
        f"Risk: *{risk}*\n"
        f"Confidence: *{confidence}%*\n\n"
        f"📌 *SMC Analysis*\n"
        f"CHoCH/BOS: `{structure_text}`\n"
        f"FVG: `{fvg}`\n"
        f"Order Block: `{order_block}`\n"
        f"Liquidity: `{liquidity}`\n"
        f"MTF Trend: `{mtf_text}`\n\n"
        "Reason:\n- " + "\n- ".join(reasons[:12]) +
        "\n\n━━━━━━━━━━━━━━━━━━\n"
        "🔥 *INFLUENCERTECH SIGNALS* 🔥\n"
        "⚠️ This is analysis only, not guaranteed profit."
    )


async def build_crypto_signal(symbol: str, vip=False):
    df = fetch_crypto_klines(symbol, "15", 150)
    mtf = {}
    for tf_label, interval in [("15m", "15"), ("1H", "60"), ("4H", "240")]:
        try:
            tf_df = fetch_crypto_klines(symbol, interval, 150)
            mtf[tf_label] = simple_trend(tf_df)
        except Exception:
            mtf[tf_label] = "Unavailable"
    return generate_signal(df, symbol, mtf=mtf, vip=vip, lock_free=not vip)



async def score_symbol(symbol: str, asset_type="crypto"):
    if asset_type == "crypto":
        df = fetch_crypto_klines(symbol, "15", 150)
        mtf = {}
        for tf_label, interval in [("15m", "15"), ("1H", "60"), ("4H", "240")]:
            try:
                tf_df = fetch_crypto_klines(symbol, interval, 150)
                mtf[tf_label] = simple_trend(tf_df)
            except Exception:
                mtf[tf_label] = "Unavailable"
        return generate_signal(df, symbol, mtf=mtf, vip=True, lock_free=False, return_meta=True)

    df = fetch_twelvedata(symbol, asset_type)
    return generate_signal(df, symbol, mtf=None, vip=True, lock_free=False, return_meta=True)


async def premium_signals(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    active, expires = is_premium(user_id)
    if not active:
        await show_premium(chat_id, user_id, context)
        return

    await context.bot.send_message(
        chat_id=chat_id,
        text="🔎 Scanning crypto, forex and stocks for premium setups..."
    )

    candidates = []

    for symbol in CRYPTO_WATCHLIST:
        try:
            meta = await score_symbol(symbol, "crypto")
            if meta["confidence"] >= PREMIUM_MIN_CONFIDENCE:
                meta["asset_type"] = "crypto"
                candidates.append(meta)
        except Exception as e:
            logger.warning("Crypto scan failed for %s: %s", symbol, e)

    if TWELVEDATA_API_KEY:
        for symbol in FOREX_WATCHLIST:
            try:
                meta = await score_symbol(symbol, "forex")
                if meta["confidence"] >= PREMIUM_MIN_CONFIDENCE:
                    meta["asset_type"] = "forex"
                    candidates.append(meta)
            except Exception as e:
                logger.warning("Forex scan failed for %s: %s", symbol, e)

        for symbol in STOCK_WATCHLIST:
            try:
                meta = await score_symbol(symbol, "stock")
                if meta["confidence"] >= PREMIUM_MIN_CONFIDENCE:
                    meta["asset_type"] = "stock"
                    candidates.append(meta)
            except Exception as e:
                logger.warning("Stock scan failed for %s: %s", symbol, e)

    candidates = sorted(candidates, key=lambda x: x["confidence"], reverse=True)[:PREMIUM_DAILY_LIMIT]

    if not candidates:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "💎 *VIP Scan Complete*\\n\\n"
                "No A-grade premium setup found right now.\\n"
                "This is good risk control — we do not force weak trades.\\n\\n"
                "Try again later."
            ),
            parse_mode="Markdown",
        )
        return

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"💎 Found *{len(candidates)}* premium setup(s). Sending now...",
        parse_mode="Markdown",
    )

    for item in candidates:
        try:
            await send_analysis(chat_id, user_id, context, item["symbol"], item["asset_type"], premium=True)
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Failed to send {item['symbol']}: {e}")


async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user.id)
    if not await has_required_access(update.effective_user.id, context):
        await send_access_gate(update.effective_chat.id, context)
        return
    await premium_signals(update.effective_chat.id, update.effective_user.id, context)


async def send_analysis(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE, symbol: str, asset_type="crypto", premium=False):
    if asset_type == "crypto":
        signal = await build_crypto_signal(symbol, vip=premium)
    elif asset_type in ["forex", "stock"]:
        df = fetch_twelvedata(symbol, asset_type)
        signal = generate_signal(df, symbol, mtf=None, vip=premium, lock_free=not premium)
    else:
        raise ValueError("Asset type must be crypto, forex, or stock.")

    await context.bot.send_message(chat_id=chat_id, text=signal, parse_mode="Markdown")


async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user.id)

    if not await has_required_access(update.effective_user.id, context):
        await send_access_gate(update.effective_chat.id, context)
        return

    if not context.args:
        await update.message.reply_text("Use: /analyze BTCUSDT\nOr just send BTCUSDT")
        return

    symbol = context.args[0].upper()
    asset_type = context.args[1].lower() if len(context.args) > 1 else "crypto"

    try:
        await send_analysis(update.effective_chat.id, update.effective_user.id, context, symbol, asset_type, premium=False)
    except Exception as e:
        logger.exception("Analyze error")
        await update.message.reply_text(f"❌ Could not analyze {symbol}. Error: {e}")


async def premium_signal(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    await premium_signals(chat_id, user_id, context)


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user.id)
    text = update.message.text.strip()

    if not await has_required_access(update.effective_user.id, context):
        await send_access_gate(update.effective_chat.id, context)
        return

    if context.user_data.get("awaiting_premium_phone"):
        await handle_premium_phone(update, context)
        return

    clean = text.upper().replace("/", "").replace("-", "").replace(" ", "")
    known_suffixes = ["USDT", "USD"]
    looks_like_symbol = clean.isalnum() and (clean.endswith(tuple(known_suffixes)) or clean in ["BTC", "ETH", "SOL", "XRP", "BNB", "DOGE"])

    if clean in ["BTC", "ETH", "SOL", "XRP", "BNB", "DOGE"]:
        clean = clean + "USDT"

    if looks_like_symbol:
        try:
            await send_analysis(update.effective_chat.id, update.effective_user.id, context, clean, "crypto", premium=False)
            return
        except Exception as e:
            await update.message.reply_text(f"❌ Could not analyze {clean}. Error: {e}")
            return

    await update.message.reply_text("Send a symbol like BTCUSDT or tap /start for menu.")


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
        "🚨 *MARKET NEWS ALERT*\n"
        "🔥 *INFLUENCERTECH SIGNALS* 🔥\n\n"
        f"Impact: *High Risk*\n"
        f"Topic: {reasons}\n\n"
        f"Headline: {item['title']}\n\n"
        "Advice: Avoid blind entries. Wait for confirmation and reduce lot size."
    )


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user.id)
    if not await has_required_access(update.effective_user.id, context):
        await send_access_gate(update.effective_chat.id, context)
        return
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
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 *Broadcast*\n🔥 *INFLUENCERTECH SIGNALS* 🔥\n\n{message}",
                parse_mode="Markdown"
            )
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
    app.add_handler(CommandHandler("premium", premium_command))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    app.job_queue.run_repeating(scheduled_news_check, interval=NEWS_CHECK_MINUTES * 60, first=20)

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
