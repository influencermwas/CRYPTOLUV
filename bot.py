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
MT5_USERS_FILE = "mt5_users.json"
MT5_ORDERS_FILE = "mt5_orders.json"
AUTO_VIP_FILE = "auto_vip_last_sent.json"

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_KEY", "") or os.getenv("SUPABASE_ANON_KEY", "")).strip()
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

VIP_HISTORY_TABLE = os.getenv("VIP_HISTORY_TABLE", "signals_vip_history").strip()
PREMIUM_TABLE = os.getenv("PREMIUM_TABLE", "signals_premium_users").strip()

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
PREMIUM_MIN_CONFIDENCE = int(os.getenv("PREMIUM_MIN_CONFIDENCE", "79") or 79)
PREMIUM_DAILY_LIMIT = int(os.getenv("PREMIUM_DAILY_LIMIT", "5") or 5)
PREMIUM_CRYPTO_SCAN_LIMIT = int(os.getenv("PREMIUM_CRYPTO_SCAN_LIMIT", "12") or 12)
PREMIUM_FOREX_SCAN_LIMIT = int(os.getenv("PREMIUM_FOREX_SCAN_LIMIT", "8") or 8)
PREMIUM_STOCK_SCAN_LIMIT = int(os.getenv("PREMIUM_STOCK_SCAN_LIMIT", "8") or 8)
VIP_LEVERAGE = float(os.getenv("VIP_LEVERAGE", "10") or 10)
AUTO_VIP_SIGNALS_ENABLED = os.getenv("AUTO_VIP_SIGNALS_ENABLED", "1").strip() == "1"
AUTO_VIP_SCAN_MINUTES = int(os.getenv("AUTO_VIP_SCAN_MINUTES", "60") or 60)
MAX_ACTIVE_MT5_ORDERS = int(os.getenv("MAX_ACTIVE_MT5_ORDERS", "4") or 4)

REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@influencertechgc").strip()
DATA_BOT_URL = os.getenv("DATA_BOT_URL", "https://t.me/INFLUENCERTECHHUB_BOT?start=5352491388").strip()

CRYPTO_WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "WLDUSDT", "CELOUSDT", "AVAXUSDT", "LINKUSDT", "TONUSDT",
    "DOTUSDT", "NEARUSDT", "OPUSDT", "ARBUSDT", "APTUSDT", "INJUSDT",
    "SUIUSDT", "TRXUSDT", "LTCUSDT", "BCHUSDT", "PEPEUSDT", "SHIBUSDT",
    "UNIUSDT", "AAVEUSDT", "FILUSDT", "ETCUSDT", "ATOMUSDT", "FETUSDT",
    "RENDERUSDT", "ICPUSDT", "MATICUSDT", "SEIUSDT", "JUPUSDT", "TIAUSDT",
]

FOREX_WATCHLIST = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CAD", "AUD/USD", "NZD/USD",
    "USD/CHF", "GBP/JPY", "EUR/JPY", "XAU/USD", "XAG/USD",
    "EUR/GBP", "EUR/AUD", "AUD/JPY", "CAD/JPY", "CHF/JPY",
]

STOCK_WATCHLIST = [
    "AAPL", "TSLA", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "AMD", "NFLX",
    "PLTR", "COIN", "MSTR", "SMCI", "AVGO", "ARM", "BABA", "JPM", "SPY", "QQQ",
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


def clean_symbol(symbol: str):
    return str(symbol or "").upper().replace("/", "").replace("-", "").replace("_", "").replace(" ", "")


def make_order_id(user_id: int, symbol: str):
    ts = now_utc().strftime("%Y%m%d%H%M%S")
    return f"VIP-{user_id}-{clean_symbol(symbol)}-{ts}"


def get_mt5_users():
    return load_json(MT5_USERS_FILE, {})


def save_mt5_users(data):
    save_json(MT5_USERS_FILE, data)


def get_mt5_orders():
    return load_json(MT5_ORDERS_FILE, [])


def save_mt5_orders(data):
    save_json(MT5_ORDERS_FILE, data)


def active_mt5_order_count(user_id: int):
    active_statuses = {"PENDING_TO_BRIDGE", "PLACED", "OPEN", "PARTIAL"}
    orders = get_mt5_orders()
    return sum(1 for o in orders if str(o.get("user_id")) == str(user_id) and o.get("status") in active_statuses)


def get_mt5_profile(user_id: int):
    return get_mt5_users().get(str(user_id), {})


def is_mt5_linked(user_id: int):
    profile = get_mt5_profile(user_id)
    return bool(profile.get("enabled") and profile.get("bridge_code"))


def mt5_lot_size(user_id: int):
    profile = get_mt5_profile(user_id)
    try:
        lot = float(profile.get("lot_size", 0.01))
    except Exception:
        lot = 0.01
    return max(0.01, lot)


def leverage_pnl_percent(direction: str, entry: float, target: float):
    if not entry:
        return 0.0
    if "SELL" in direction:
        move_pct = ((entry - target) / entry) * 100
    else:
        move_pct = ((target - entry) / entry) * 100
    return move_pct * VIP_LEVERAGE


def queue_mt5_pending_order(user_id: int, asset_type: str, meta: dict):
    """Queue a VIP signal for the user's laptop MT5 bridge. The laptop bridge pulls these orders."""
    if not is_mt5_linked(user_id):
        return {"queued": False, "reason": "MT5 not linked"}

    active_count = active_mt5_order_count(user_id)
    if active_count >= MAX_ACTIVE_MT5_ORDERS:
        return {"queued": False, "reason": f"Maximum {MAX_ACTIVE_MT5_ORDERS} active MT5 orders reached"}

    profile = get_mt5_profile(user_id)
    direction = meta.get("direction", "")
    entry = (float(meta.get("entry_low")) + float(meta.get("entry_high"))) / 2

    order = {
        "order_id": make_order_id(user_id, meta.get("symbol")),
        "user_id": str(user_id),
        "bridge_code": profile.get("bridge_code"),
        "asset_type": asset_type,
        "symbol": meta.get("symbol"),
        "direction": direction,
        "order_type": "BUY_LIMIT" if "BUY" in direction else "SELL_LIMIT" if "SELL" in direction else "NONE",
        "lot_size": mt5_lot_size(user_id),
        "entry_price": entry,
        "entry_low": meta.get("entry_low"),
        "entry_high": meta.get("entry_high"),
        "stop_loss": meta.get("stop_loss"),
        "tp1": meta.get("tp1"),
        "tp2": meta.get("tp2"),
        "tp3": meta.get("tp3"),
        "leverage_used_for_display": VIP_LEVERAGE,
        "tp1_pnl_percent": round(leverage_pnl_percent(direction, entry, float(meta.get("tp1"))), 2),
        "tp2_pnl_percent": round(leverage_pnl_percent(direction, entry, float(meta.get("tp2"))), 2),
        "tp3_pnl_percent": round(leverage_pnl_percent(direction, entry, float(meta.get("tp3"))), 2),
        "sl_pnl_percent": round(leverage_pnl_percent(direction, entry, float(meta.get("stop_loss"))), 2),
        "confidence": meta.get("confidence"),
        "status": "PENDING_TO_BRIDGE",
        "created_at": now_utc().isoformat(),
        "updated_at": now_utc().isoformat(),
    }
    orders = get_mt5_orders()
    orders.append(order)
    save_mt5_orders(orders[-1000:])
    return {"queued": True, "order": order}


def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def sb_url(table: str):
    return f"{SUPABASE_URL}/rest/v1/{table}"


def sb_get(table: str, params=None):
    if not USE_SUPABASE:
        return None
    try:
        r = requests.get(sb_url(table), headers=sb_headers(), params=params or {}, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning("Supabase GET failed %s: %s", table, e)
        return None


def sb_post(table: str, payload: dict):
    if not USE_SUPABASE:
        return None
    try:
        r = requests.post(sb_url(table), headers=sb_headers(), json=payload, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning("Supabase POST failed %s: %s", table, e)
        return None


def sb_patch(table: str, params: dict, payload: dict):
    if not USE_SUPABASE:
        return None
    try:
        r = requests.patch(sb_url(table), headers=sb_headers(), params=params, json=payload, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning("Supabase PATCH failed %s: %s", table, e)
        return None


def sb_upsert(table: str, payload: dict, conflict="user_id"):
    if not USE_SUPABASE:
        return None
    headers = sb_headers()
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"
    try:
        r = requests.post(sb_url(table), headers=headers, params={"on_conflict": conflict}, json=payload, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning("Supabase UPSERT failed %s: %s", table, e)
        return None


def register_user(user_id: int):
    """Register user locally. Returns True if first time in local users.json."""
    users = load_json(USERS_FILE, [])
    is_new = user_id not in users
    if is_new:
        users.append(user_id)
        save_json(USERS_FILE, users)
    return is_new


def get_premium_row(user_id: int):
    rows = sb_get(PREMIUM_TABLE, {"user_id": f"eq.{user_id}", "select": "*", "limit": "1"})
    if rows:
        return rows[0]
    return None


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def is_premium(user_id: int):
    if USE_SUPABASE:
        row = get_premium_row(user_id)
        expires_dt = parse_dt(row.get("expires_at")) if row else None
        if expires_dt and expires_dt > now_utc():
            return True, expires_dt
        return False, expires_dt

    premium = load_json(PREMIUM_FILE, {})
    expires = premium.get(str(user_id))
    if not expires:
        return False, None
    expires_dt = parse_dt(expires)
    if expires_dt and expires_dt > now_utc():
        return True, expires_dt
    return False, expires_dt


def activate_premium(user_id: int, hours=24, source="paid", mark_trial_used=False):
    expires_dt = now_utc() + timedelta(hours=hours)

    if USE_SUPABASE:
        payload = {
            "user_id": str(user_id),
            "expires_at": expires_dt.isoformat(),
            "source": source,
            "remind_6h_sent": False,
            "remind_1h_sent": False,
            "expired_notice_sent": False,
            "updated_at": now_utc().isoformat(),
        }
        if mark_trial_used:
            payload["trial_used"] = True
        sb_upsert(PREMIUM_TABLE, payload)

    premium = load_json(PREMIUM_FILE, {})
    premium[str(user_id)] = expires_dt.isoformat()
    save_json(PREMIUM_FILE, premium)
    return expires_dt


def ensure_free_trial(user_id: int):
    """Give 24h free trial once per user. Returns expiry if trial was created."""
    if USE_SUPABASE:
        row = get_premium_row(user_id)
        if row and row.get("trial_used"):
            return None
        active, _ = is_premium(user_id)
        if active:
            # Still mark trial used so it cannot be claimed after paid premium expires.
            sb_upsert(PREMIUM_TABLE, {"user_id": str(user_id), "trial_used": True, "updated_at": now_utc().isoformat()})
            return None
        return activate_premium(user_id, 24, source="free_trial", mark_trial_used=True)

    trials = load_json("trial_users.json", [])
    if user_id in trials:
        return None
    trials.append(user_id)
    save_json("trial_users.json", trials)
    return activate_premium(user_id, 24, source="free_trial")



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
        [
            InlineKeyboardButton("📜 VIP History", callback_data="vip_history"),
            InlineKeyboardButton("📊 VIP Performance", callback_data="vip_performance"),
        ],
        [InlineKeyboardButton("📰 Market News", callback_data="news")],
        [InlineKeyboardButton("⚠️ Risk Rules", callback_data="risk")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user.id)

    if not await has_required_access(update.effective_user.id, context):
        await send_access_gate(update.effective_chat.id, context)
        return

    trial_expires = ensure_free_trial(update.effective_user.id)
    active, expires = is_premium(update.effective_user.id)
    if trial_expires:
        premium_text = f"🎁 Free 24-hour Premium Trial active until `{trial_expires.strftime('%Y-%m-%d %H:%M UTC')}`"
    else:
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
            trial_expires = ensure_free_trial(query.from_user.id)
            trial_text = f"\n🎁 Free 24-hour Premium Trial activated until {trial_expires.strftime('%Y-%m-%d %H:%M UTC')}." if trial_expires else ""
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="✅ Access verified. Welcome to INFLUENCERTECH SIGNALS." + trial_text,
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
    elif data == "vip_history":
        await send_vip_history(query.message.chat_id, query.from_user.id, context)
    elif data == "vip_performance":
        await send_vip_performance(query.message.chat_id, query.from_user.id, context)
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
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Get VIP Signals", callback_data="vip_signal")], [InlineKeyboardButton("📜 History", callback_data="vip_history"), InlineKeyboardButton("📊 Performance", callback_data="vip_performance")]])
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
            "time": datetime.fromtimestamp(int(c[0]) / 1000, tz=timezone.utc).isoformat(),
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


def finnhub_symbol(symbol: str, asset_type: str):
    clean = symbol.upper().replace("/", "").replace("-", "").replace("_", "").replace(" ", "")

    forex_map = {
        "EURUSD": "OANDA:EUR_USD",
        "GBPUSD": "OANDA:GBP_USD",
        "USDJPY": "OANDA:USD_JPY",
        "USDCAD": "OANDA:USD_CAD",
        "AUDUSD": "OANDA:AUD_USD",
        "NZDUSD": "OANDA:NZD_USD",
        "USDCHF": "OANDA:USD_CHF",
        "GBPJPY": "OANDA:GBP_JPY",
        "EURJPY": "OANDA:EUR_JPY",
        "XAUUSD": "OANDA:XAU_USD",
        "XAGUSD": "OANDA:XAG_USD",
    }

    if asset_type == "forex":
        return forex_map.get(clean, f"OANDA:{clean[:3]}_{clean[3:]}")

    return clean


def finnhub_resolution(interval="15"):
    interval = str(interval).lower()
    if interval in ["1", "3", "5", "15", "30", "60"]:
        return interval
    if interval in ["1h", "h"]:
        return "60"
    if interval in ["1d", "d", "day"]:
        return "D"
    return "15"


def fetch_twelvedata(symbol: str, asset_type: str, interval="15min", outputsize=150):
    """
    Uses Twelve Data for forex and stocks.
    Crypto still uses OKX through fetch_crypto_klines().
    """
    if not TWELVEDATA_API_KEY:
        raise ValueError("TWELVEDATA_API_KEY is missing. Add it in Render Environment Variables.")

    asset_type = (asset_type or "stock").lower().strip()

    if asset_type == "forex":
        clean = symbol.upper().replace("/", "").replace("-", "").replace("_", "").replace(" ", "")
        if len(clean) == 6:
            td_symbol = f"{clean[:3]}/{clean[3:]}"
        else:
            td_symbol = symbol.upper()
    else:
        td_symbol = symbol.upper().replace(" ", "")

    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": td_symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVEDATA_API_KEY,
    }

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    if data.get("status") == "error":
        raise ValueError(data.get("message", f"Twelve Data returned an error for {td_symbol}"))

    values = data.get("values", [])
    if not values:
        raise ValueError(f"No Twelve Data candle data returned for {td_symbol}")

    rows = []
    for item in reversed(values):
        rows.append({
            "time": item.get("datetime"),
            "open": float(item["open"]),
            "high": float(item["high"]),
            "low": float(item["low"]),
            "close": float(item["close"]),
            "volume": float(item.get("volume") or 0),
        })

    df = pd.DataFrame(rows)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna().tail(outputsize).reset_index(drop=True)

    if len(df) < 50:
        raise ValueError(f"Not enough Twelve Data candle data for {td_symbol}")

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
            "current_price": close,
            "entry_low": entry_low,
            "entry_high": entry_high,
            "stop_loss": stop,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "support": support,
            "resistance": resistance,
            "leverage_used_for_display": VIP_LEVERAGE,
            "created_at": now_utc().isoformat(),
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
        entry_mid = (entry_low + entry_high) / 2
        tp1_pnl = leverage_pnl_percent(direction, entry_mid, tp1)
        tp2_pnl = leverage_pnl_percent(direction, entry_mid, tp2)
        tp3_pnl = leverage_pnl_percent(direction, entry_mid, tp3)
        sl_pnl = leverage_pnl_percent(direction, entry_mid, stop)
        extra_vip = (
            f"Take Profit 3: `{tp3:.6g}`\n"
            f"Risk Reward: `Approx 1:{abs((tp2-close)/(close-stop)):.2f}`\n\n"
            f"📈 *{VIP_LEVERAGE:g}x Futures PnL Projection*\n"
            f"TP1 Profit: `{tp1_pnl:+.2f}%`\n"
            f"TP2 Profit: `{tp2_pnl:+.2f}%`\n"
            f"TP3 Profit: `{tp3_pnl:+.2f}%`\n"
            f"SL Risk: `{sl_pnl:+.2f}%`\n\n"
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




def save_vip_signal(user_id: int, asset_type: str, meta: dict):
    if not USE_SUPABASE or meta.get("direction") == "WAIT":
        return
    payload = {
        "user_id": str(user_id),
        "symbol": meta.get("symbol"),
        "asset_type": asset_type,
        "direction": meta.get("direction"),
        "entry_low": meta.get("entry_low"),
        "entry_high": meta.get("entry_high"),
        "stop_loss": meta.get("stop_loss"),
        "tp1": meta.get("tp1"),
        "tp2": meta.get("tp2"),
        "tp3": meta.get("tp3"),
        "confidence": meta.get("confidence"),
        "status": "RUNNING",
        "profit_percent": 0,
        "created_at": now_utc().isoformat(),
        "updated_at": now_utc().isoformat(),
    }
    sb_post(VIP_HISTORY_TABLE, payload)


def fetch_for_asset(symbol: str, asset_type: str):
    if asset_type == "crypto":
        return fetch_crypto_klines(symbol, "15", 150)
    return fetch_twelvedata(symbol, asset_type)


def evaluate_signal_outcome(row: dict):
    try:
        df = fetch_for_asset(row["symbol"], row.get("asset_type", "crypto"))
        created = parse_dt(row.get("created_at")) or (now_utc() - timedelta(days=3))
        if "time" in df.columns:
            df["_time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
            df = df[df["_time"] >= created]
        if df.empty:
            return None

        direction = row.get("direction", "")
        stop = float(row.get("stop_loss"))
        tp1 = float(row.get("tp1"))
        tp2 = float(row.get("tp2"))
        tp3 = float(row.get("tp3"))
        entry_mid = (float(row.get("entry_low")) + float(row.get("entry_high"))) / 2

        for _, c in df.iterrows():
            high = float(c["high"])
            low = float(c["low"])
            if "BUY" in direction:
                if low <= stop:
                    return "LOSS", round(((stop - entry_mid) / entry_mid) * 100, 2)
                if high >= tp3:
                    return "WIN", round(((tp3 - entry_mid) / entry_mid) * 100, 2)
                if high >= tp2:
                    return "WIN", round(((tp2 - entry_mid) / entry_mid) * 100, 2)
                if high >= tp1:
                    return "WIN", round(((tp1 - entry_mid) / entry_mid) * 100, 2)
            elif "SELL" in direction:
                if high >= stop:
                    return "LOSS", round(((entry_mid - stop) / entry_mid) * 100, 2)
                if low <= tp3:
                    return "WIN", round(((entry_mid - tp3) / entry_mid) * 100, 2)
                if low <= tp2:
                    return "WIN", round(((entry_mid - tp2) / entry_mid) * 100, 2)
                if low <= tp1:
                    return "WIN", round(((entry_mid - tp1) / entry_mid) * 100, 2)
    except Exception as e:
        logger.warning("Signal outcome check failed: %s", e)
    return None


async def update_vip_results(context: ContextTypes.DEFAULT_TYPE = None):
    if not USE_SUPABASE:
        return
    rows = sb_get(VIP_HISTORY_TABLE, {"status": "eq.RUNNING", "select": "*", "limit": "100"}) or []
    for row in rows:
        result = evaluate_signal_outcome(row)
        if not result:
            continue
        status, profit_percent = result
        sb_patch(VIP_HISTORY_TABLE, {"id": f"eq.{row['id']}"}, {
            "status": status,
            "profit_percent": profit_percent,
            "updated_at": now_utc().isoformat(),
        })


async def send_vip_history(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    await update_vip_results(context)
    if not USE_SUPABASE:
        await context.bot.send_message(chat_id=chat_id, text="📜 VIP history needs Supabase env variables configured.")
        return
    rows = sb_get(VIP_HISTORY_TABLE, {
        "user_id": f"eq.{user_id}",
        "select": "*",
        "order": "created_at.desc",
        "limit": "10",
    }) or []
    if not rows:
        await context.bot.send_message(chat_id=chat_id, text="📜 No VIP signal history yet. Request VIP signals first.")
        return
    lines = ["📜 *Your Last VIP Signals*\n"]
    for r in rows:
        icon = "✅" if r.get("status") == "WIN" else "❌" if r.get("status") == "LOSS" else "⏳"
        profit = float(r.get("profit_percent") or 0)
        lines.append(f"{icon} `{r.get('symbol')}` {r.get('direction')} | {r.get('status')} | {profit:+.2f}%")
    await context.bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode="Markdown")


async def send_vip_performance(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE, admin_all=False):
    await update_vip_results(context)
    if not USE_SUPABASE:
        await context.bot.send_message(chat_id=chat_id, text="📊 VIP performance needs Supabase env variables configured.")
        return
    params = {"select": "*", "limit": "500"}
    if not admin_all:
        params["user_id"] = f"eq.{user_id}"
    rows = sb_get(VIP_HISTORY_TABLE, params) or []
    if not rows:
        await context.bot.send_message(chat_id=chat_id, text="📊 No VIP performance data yet.")
        return

    closed = [r for r in rows if r.get("status") in ["WIN", "LOSS"]]
    wins = sum(1 for r in closed if r.get("status") == "WIN")
    losses = sum(1 for r in closed if r.get("status") == "LOSS")
    running = sum(1 for r in rows if r.get("status") == "RUNNING")
    total_pct = sum(float(r.get("profit_percent") or 0) for r in closed)
    win_rate = round((wins / len(closed)) * 100, 1) if closed else 0

    yesterday = (now_utc() - timedelta(days=1)).date()
    y_rows = [r for r in closed if parse_dt(r.get("created_at")) and parse_dt(r.get("created_at")).date() == yesterday]
    y_pct = sum(float(r.get("profit_percent") or 0) for r in y_rows)
    y_wins = sum(1 for r in y_rows if r.get("status") == "WIN")
    y_losses = sum(1 for r in y_rows if r.get("status") == "LOSS")

    text = (
        "📊 *VIP Signal Performance*\n\n"
        f"Yesterday: *{y_wins} Wins*, *{y_losses} Losses* `({y_pct:+.2f}%)`\n"
        f"All Time: *{wins} Wins*, *{losses} Losses*, *{running} Running*\n"
        f"Win Rate: *{win_rate}%*\n"
        f"Total Result: `{total_pct:+.2f}%`\n\n"
        "⚠️ Percentages are based on signal entry to TP/SL movement."
    )
    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")


async def vip_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user.id)
    await send_vip_history(update.effective_chat.id, update.effective_user.id, context)


async def vip_performance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user.id)
    admin_all = update.effective_user.id == ADMIN_ID and context.args and context.args[0].lower() == "all"
    await send_vip_performance(update.effective_chat.id, update.effective_user.id, context, admin_all=admin_all)


async def givepremium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only.")
        return
    if not context.args:
        await update.message.reply_text("Use: /givepremium USER_ID 24\nExample: /givepremium 123456789 72")
        return
    try:
        target_user = int(context.args[0])
        hours = 24
        if len(context.args) >= 2:
            raw = context.args[1].lower().strip()
            if raw.endswith("d"):
                hours = int(raw.replace("d", "")) * 24
            else:
                hours = int(raw)
        expires = activate_premium(target_user, hours, source="admin")
        await update.message.reply_text(f"✅ Premium activated for {target_user} until {expires.strftime('%Y-%m-%d %H:%M UTC')}.")
        try:
            await context.bot.send_message(
                chat_id=target_user,
                text=f"✅ *Premium activated by admin!*\n\nExpires: `{expires.strftime('%Y-%m-%d %H:%M UTC')}`",
                parse_mode="Markdown",
            )
        except Exception:
            pass
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")


async def premium_expiry_reminder_check(context: ContextTypes.DEFAULT_TYPE):
    if not USE_SUPABASE:
        return
    rows = sb_get(PREMIUM_TABLE, {"select": "*", "limit": "1000"}) or []
    current = now_utc()
    for row in rows:
        user_id = int(row["user_id"])
        expires = parse_dt(row.get("expires_at"))
        if not expires:
            continue
        remaining = expires - current
        patch = {}
        try:
            if timedelta(hours=1) < remaining <= timedelta(hours=6) and not row.get("remind_6h_sent"):
                await context.bot.send_message(chat_id=user_id, text="⏰ Your Premium expires in about 6 hours. Renew to continue enjoying VIP signals.")
                patch["remind_6h_sent"] = True
            elif timedelta(0) < remaining <= timedelta(hours=1) and not row.get("remind_1h_sent"):
                await context.bot.send_message(chat_id=user_id, text="⏰ Your Premium expires in about 1 hour. Renew now to avoid interruption.")
                patch["remind_1h_sent"] = True
            elif remaining <= timedelta(0) and not row.get("expired_notice_sent"):
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(f"💳 Renew Premium KSh {PREMIUM_PRICE}", callback_data="pay_premium")]])
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        "❌ *Premium subscription ended.*\n\n"
                        "Renew to continue enjoying:\n"
                        "• VIP Crypto Signals\n• Forex Signals\n• Stock Signals\n• SMC Analysis\n• High-confidence Setups"
                    ),
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
                patch["expired_notice_sent"] = True
            if patch:
                patch["updated_at"] = now_utc().isoformat()
                sb_patch(PREMIUM_TABLE, {"user_id": f"eq.{user_id}"}, patch)
        except Exception as e:
            logger.warning("Premium reminder failed for %s: %s", user_id, e)


def get_active_premium_user_ids():
    ids = set()
    if USE_SUPABASE:
        rows = sb_get(PREMIUM_TABLE, {"select": "user_id,expires_at", "limit": "1000"}) or []
        for row in rows:
            expires = parse_dt(row.get("expires_at"))
            if expires and expires > now_utc():
                try:
                    ids.add(int(row.get("user_id")))
                except Exception:
                    pass
    local = load_json(PREMIUM_FILE, {})
    for uid, expires_raw in local.items():
        expires = parse_dt(expires_raw)
        if expires and expires > now_utc():
            try:
                ids.add(int(uid))
            except Exception:
                pass
    return sorted(ids)


async def automatic_vip_signal_check(context: ContextTypes.DEFAULT_TYPE):
    if not AUTO_VIP_SIGNALS_ENABLED:
        return
    users = get_active_premium_user_ids()
    if not users:
        return
    last_sent = load_json(AUTO_VIP_FILE, {})
    current = now_utc()
    for user_id in users:
        last = parse_dt(last_sent.get(str(user_id)))
        if last and current - last < timedelta(minutes=AUTO_VIP_SCAN_MINUTES):
            continue
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="💎 Automatic VIP scan running. You do not need to press Get VIP Signals.",
            )
            await premium_signals(user_id, user_id, context)
            last_sent[str(user_id)] = current.isoformat()
            save_json(AUTO_VIP_FILE, last_sent)
        except Exception as e:
            logger.warning("Automatic VIP scan failed for %s: %s", user_id, e)


async def maintenance_check(context: ContextTypes.DEFAULT_TYPE):
    await update_vip_results(context)
    await premium_expiry_reminder_check(context)
    await automatic_vip_signal_check(context)

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

    for symbol in CRYPTO_WATCHLIST[:PREMIUM_CRYPTO_SCAN_LIMIT]:
        try:
            meta = await score_symbol(symbol, "crypto")
            if meta["confidence"] >= PREMIUM_MIN_CONFIDENCE and meta["direction"] != "WAIT":
                meta["asset_type"] = "crypto"
                candidates.append(meta)
        except Exception as e:
            logger.warning("Crypto scan failed for %s: %s", symbol, e)

    if TWELVEDATA_API_KEY:
        for symbol in FOREX_WATCHLIST[:PREMIUM_FOREX_SCAN_LIMIT]:
            try:
                meta = await score_symbol(symbol, "forex")
                if meta["confidence"] >= PREMIUM_MIN_CONFIDENCE and meta["direction"] != "WAIT":
                    meta["asset_type"] = "forex"
                    candidates.append(meta)
            except Exception as e:
                logger.warning("Forex scan failed for %s: %s", symbol, e)

        for symbol in STOCK_WATCHLIST[:PREMIUM_STOCK_SCAN_LIMIT]:
            try:
                meta = await score_symbol(symbol, "stock")
                if meta["confidence"] >= PREMIUM_MIN_CONFIDENCE and meta["direction"] != "WAIT":
                    meta["asset_type"] = "stock"
                    candidates.append(meta)
            except Exception as e:
                logger.warning("Stock scan failed for %s: %s", symbol, e)

    candidates = sorted(candidates, key=lambda x: x["confidence"], reverse=True)[:PREMIUM_DAILY_LIMIT]

    if not candidates:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "💎 *VIP Scan Complete*\n\n"
                "No A-grade premium setup found right now.\n"
                "This is good risk control — we do not force weak trades.\n\n"
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
    meta = None
    if asset_type == "crypto":
        signal = await build_crypto_signal(symbol, vip=premium)
        if premium:
            df = fetch_crypto_klines(symbol, "15", 150)
            mtf = {}
            for tf_label, interval in [("15m", "15"), ("1H", "60"), ("4H", "240")]:
                try:
                    mtf[tf_label] = simple_trend(fetch_crypto_klines(symbol, interval, 150))
                except Exception:
                    mtf[tf_label] = "Unavailable"
            meta = generate_signal(df, symbol, mtf=mtf, vip=True, lock_free=False, return_meta=True)
    elif asset_type in ["forex", "stock"]:
        df = fetch_twelvedata(symbol, asset_type)
        signal = generate_signal(df, symbol, mtf=None, vip=premium, lock_free=not premium)
        if premium:
            meta = generate_signal(df, symbol, mtf=None, vip=True, lock_free=False, return_meta=True)
    else:
        raise ValueError("Asset type must be crypto, forex, or stock.")

    await context.bot.send_message(chat_id=chat_id, text=signal, parse_mode="Markdown")
    if premium and meta:
        save_vip_signal(user_id, asset_type, meta)
        mt5_result = queue_mt5_pending_order(user_id, asset_type, meta)
        if mt5_result.get("queued"):
            order = mt5_result["order"]
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "🤖 *MT5 Auto Order Queued*\n\n"
                    f"Symbol: `{order['symbol']}`\n"
                    f"Type: `{order['order_type']}`\n"
                    f"Lot Size: `{order['lot_size']}`\n"
                    f"Entry: `{order['entry_price']:.6g}`\n"
                    f"SL: `{float(order['stop_loss']):.6g}`\n"
                    f"TP1: `{float(order['tp1']):.6g}`\n\n"
                    "Keep your laptop, MT5, and MT5 Bridge running for execution."
                ),
                parse_mode="Markdown",
            )
        elif is_mt5_linked(user_id):
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ MT5 auto-order skipped: {mt5_result.get('reason')}",
            )


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


async def setlot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("Use: /setlot 0.01")
        return
    try:
        lot = float(context.args[0])
        if lot <= 0:
            raise ValueError("Lot size must be above 0")
        users = get_mt5_users()
        profile = users.get(str(update.effective_user.id), {})
        profile["lot_size"] = lot
        profile.setdefault("enabled", False)
        profile["updated_at"] = now_utc().isoformat()
        users[str(update.effective_user.id)] = profile
        save_mt5_users(users)
        await update.message.reply_text(f"✅ MT5 lot size saved: {lot}")
    except Exception as e:
        await update.message.reply_text(f"❌ Invalid lot size. Example: /setlot 0.01\nError: {e}")


async def mt5link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user.id)
    users = get_mt5_users()
    uid = str(update.effective_user.id)
    profile = users.get(uid, {})
    code = profile.get("bridge_code") or f"BRIDGE-{uid[-6:]}-{now_utc().strftime('%H%M%S')}"
    profile["bridge_code"] = code
    profile["enabled"] = True
    profile.setdefault("lot_size", 0.01)
    profile["updated_at"] = now_utc().isoformat()
    users[uid] = profile
    save_mt5_users(users)
    await update.message.reply_text(
        "✅ *MT5 Bridge Enabled*\n\n"
        f"Bridge Code: `{code}`\n"
        f"Lot Size: `{profile.get('lot_size', 0.01)}`\n"
        f"Max Active Orders: `{MAX_ACTIVE_MT5_ORDERS}`\n\n"
        "Keep your laptop, MT5, and MT5 Bridge running.\n"
        "Use /setlot 0.01 to change lot size.\n"
        "Use /mt5off to disable auto orders.",
        parse_mode="Markdown",
    )


async def mt5status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user.id)
    profile = get_mt5_profile(update.effective_user.id)
    active_count = active_mt5_order_count(update.effective_user.id)
    if not profile:
        await update.message.reply_text("MT5 Bridge is not linked. Use /mt5link first.")
        return
    await update.message.reply_text(
        "🤖 *MT5 Status*\n\n"
        f"Enabled: `{profile.get('enabled', False)}`\n"
        f"Bridge Code: `{profile.get('bridge_code', 'None')}`\n"
        f"Lot Size: `{profile.get('lot_size', 0.01)}`\n"
        f"Active/Pending Orders: `{active_count}/{MAX_ACTIVE_MT5_ORDERS}`",
        parse_mode="Markdown",
    )


async def mt5off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_mt5_users()
    uid = str(update.effective_user.id)
    profile = users.get(uid, {})
    profile["enabled"] = False
    profile["updated_at"] = now_utc().isoformat()
    users[uid] = profile
    save_mt5_users(users)
    await update.message.reply_text("✅ MT5 auto orders disabled. VIP signals will still be sent normally.")


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

    clean = text.upper().replace("/", "").replace("-", "").replace("_", "").replace(" ", "")

    crypto_shortcuts = [s.replace("USDT", "") for s in CRYPTO_WATCHLIST]
    forex_symbols = [s.replace("/", "") for s in FOREX_WATCHLIST]
    stock_symbols = STOCK_WATCHLIST

    if clean in crypto_shortcuts:
        clean = clean + "USDT"

    try:
        if clean.endswith("USDT"):
            await send_analysis(update.effective_chat.id, update.effective_user.id, context, clean, "crypto", premium=False)
            return

        if clean in forex_symbols:
            await send_analysis(update.effective_chat.id, update.effective_user.id, context, clean, "forex", premium=False)
            return

        if clean in stock_symbols or (clean.isalpha() and 1 <= len(clean) <= 5):
            await send_analysis(update.effective_chat.id, update.effective_user.id, context, clean, "stock", premium=False)
            return

    except Exception as e:
        await update.message.reply_text(f"❌ Could not analyze {clean}. Error: {e}")
        return

    await update.message.reply_text("Send a symbol like BTCUSDT, EURUSD, XAUUSD, AAPL or tap /start for menu.")


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


async def adminstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only.")
        return

    users = load_json(USERS_FILE, [])
    premium = load_json(PREMIUM_FILE, {})

    running = wins = losses = 0
    if USE_SUPABASE:
        rows = sb_get(VIP_HISTORY_TABLE, {"select": "status", "limit": "1000"}) or []
        running = sum(1 for r in rows if r.get("status") == "RUNNING")
        wins = sum(1 for r in rows if r.get("status") == "WIN")
        losses = sum(1 for r in rows if r.get("status") == "LOSS")
    total_closed = wins + losses
    win_rate = round((wins / total_closed) * 100, 1) if total_closed else 0

    text = (
        "📊 *ADMIN STATS*\n\n"
        f"👥 Users: *{len(users)}*\n"
        f"💎 Premium Users: *{len(premium)}*\n"
        f"📈 Crypto Scan Limit: *{PREMIUM_CRYPTO_SCAN_LIMIT}*\n"
        f"💱 Forex Scan Limit: *{PREMIUM_FOREX_SCAN_LIMIT}*\n"
        f"🏛 Stock Scan Limit: *{PREMIUM_STOCK_SCAN_LIMIT}*\n"
        f"🎯 Daily VIP Limit: *{PREMIUM_DAILY_LIMIT}*\n"
        f"📊 VIP Min Confidence: *{PREMIUM_MIN_CONFIDENCE}%*\n"
        f"⚡ VIP Leverage Display: *{VIP_LEVERAGE:g}x*\n"
        f"🤖 Auto VIP: *{AUTO_VIP_SIGNALS_ENABLED}* every *{AUTO_VIP_SCAN_MINUTES} min*\n"
        f"🧾 Max MT5 Orders/User: *{MAX_ACTIVE_MT5_ORDERS}*\n\n"
        f"🏃 Running Signals: *{running}*\n"
        f"✅ Wins: *{wins}*\n"
        f"❌ Losses: *{losses}*\n"
        f"📌 Win Rate: *{win_rate}%*"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN missing. Add it in .env or Render Environment Variables.")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analyze", analyze))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("premium", premium_command))
    app.add_handler(CommandHandler("givepremium", givepremium))
    app.add_handler(CommandHandler("viphistory", vip_history_command))
    app.add_handler(CommandHandler("vipperformance", vip_performance_command))
    app.add_handler(CommandHandler("adminstats", adminstats))
    app.add_handler(CommandHandler("setlot", setlot))
    app.add_handler(CommandHandler("mt5link", mt5link))
    app.add_handler(CommandHandler("mt5status", mt5status))
    app.add_handler(CommandHandler("mt5off", mt5off))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    app.job_queue.run_repeating(scheduled_news_check, interval=NEWS_CHECK_MINUTES * 60, first=20)
    app.job_queue.run_repeating(maintenance_check, interval=15 * 60, first=60)

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
