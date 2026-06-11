import os
import asyncio
import logging
import json

import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

import bot as bot_module

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = getattr(bot_module, "BOT_TOKEN", os.getenv("BOT_TOKEN", "").strip())
PUBLIC_URL = os.getenv("PUBLIC_URL", "").strip().rstrip("/")
CRON_SECRET = os.getenv("CRON_SECRET", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing. Add it in Render Environment Variables.")


async def fallback_adminstats(update, context):
    """Safe fallback so app.py never crashes if bot.py is missing adminstats."""
    admin_id = getattr(bot_module, "ADMIN_ID", 0)
    if update.effective_user.id != admin_id:
        await update.message.reply_text("❌ Admin only.")
        return

    load_json = getattr(bot_module, "load_json", lambda path, default: default)
    users_file = getattr(bot_module, "USERS_FILE", "users.json")
    premium_file = getattr(bot_module, "PREMIUM_FILE", "premium_users.json")
    users = load_json(users_file, [])
    premium = load_json(premium_file, {})

    text = (
        "📊 ADMIN STATS\n\n"
        f"👥 Users: {len(users)}\n"
        f"💎 Premium Users: {len(premium)}\n"
        f"📈 Crypto Scan Limit: {getattr(bot_module, 'PREMIUM_CRYPTO_SCAN_LIMIT', 'N/A')}\n"
        f"💱 Forex Scan Limit: {getattr(bot_module, 'PREMIUM_FOREX_SCAN_LIMIT', 'N/A')}\n"
        f"🏛 Stock Scan Limit: {getattr(bot_module, 'PREMIUM_STOCK_SCAN_LIMIT', 'N/A')}\n"
        f"🎯 Daily VIP Limit: {getattr(bot_module, 'PREMIUM_DAILY_LIMIT', 'N/A')}"
    )
    await update.message.reply_text(text)


# Pull handlers from bot.py. adminstats has a fallback to prevent ImportError crashes.
start = bot_module.start
analyze = bot_module.analyze
news_command = bot_module.news_command
broadcast = bot_module.broadcast
premium_command = bot_module.premium_command
referral_command = getattr(bot_module, "referral_command", None)
givepremium = bot_module.givepremium
vip_history_command = bot_module.vip_history_command
vip_performance_command = bot_module.vip_performance_command
adminstats = getattr(bot_module, "adminstats", fallback_adminstats)

setlot = getattr(bot_module, "setlot", None)
setmaxtrades = getattr(bot_module, "setmaxtrades", None)
mt5link = getattr(bot_module, "mt5link", None)
mt5status = getattr(bot_module, "mt5status", None)
mt5off = getattr(bot_module, "mt5off", None)
clearmt5 = getattr(bot_module, "clearmt5", None)
mt5queue = getattr(bot_module, "mt5queue", None)

button_click = bot_module.button_click
text_handler = bot_module.text_handler
scheduled_news_check = bot_module.scheduled_news_check
maintenance_check = bot_module.maintenance_check
handle_mpesa_callback = bot_module.handle_mpesa_callback

telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("analyze", analyze))
telegram_app.add_handler(CommandHandler("news", news_command))
telegram_app.add_handler(CommandHandler("broadcast", broadcast))
telegram_app.add_handler(CommandHandler("premium", premium_command))
if referral_command:
    telegram_app.add_handler(CommandHandler("referral", referral_command))
telegram_app.add_handler(CommandHandler("givepremium", givepremium))
telegram_app.add_handler(CommandHandler("viphistory", vip_history_command))
telegram_app.add_handler(CommandHandler("vipperformance", vip_performance_command))
telegram_app.add_handler(CommandHandler("adminstats", adminstats))

if setlot:
    telegram_app.add_handler(CommandHandler("setlot", setlot))
if setmaxtrades:
    telegram_app.add_handler(CommandHandler("setmaxtrades", setmaxtrades))
if mt5link:
    telegram_app.add_handler(CommandHandler("mt5link", mt5link))
if mt5status:
    telegram_app.add_handler(CommandHandler("mt5status", mt5status))
if mt5off:
    telegram_app.add_handler(CommandHandler("mt5off", mt5off))
if clearmt5:
    telegram_app.add_handler(CommandHandler("clearmt5", clearmt5))
if mt5queue:
    telegram_app.add_handler(CommandHandler("mt5queue", mt5queue))

telegram_app.add_handler(CallbackQueryHandler(button_click))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(telegram_app.initialize())
loop.run_until_complete(telegram_app.start())

app = Flask(__name__)


@app.get("/")
def home():
    return "INFLUENCERTECH SIGNALS Bot is running ✅"


@app.post("/webhook")
def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, telegram_app.bot)
        loop.run_until_complete(telegram_app.process_update(update))
        return jsonify({"ok": True})
    except Exception as e:
        logger.exception("Webhook error")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/set_webhook")
def set_webhook():
    if not PUBLIC_URL:
        return jsonify({"ok": False, "error": "PUBLIC_URL is missing in environment variables"}), 400

    webhook_url = f"{PUBLIC_URL}/webhook"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    response = requests.post(url, json={"url": webhook_url}, timeout=20)

    try:
        commands = [
            BotCommand("start", "Open main menu"),
            BotCommand("analyze", "Analyze crypto, forex or stock"),
            BotCommand("news", "Check market news alerts"),
            BotCommand("premium", "Get premium VIP signals"),
            BotCommand("referral", "View referral link and rewards"),
            BotCommand("viphistory", "View VIP signal history"),
            BotCommand("vipperformance", "View VIP win/loss performance"),
            BotCommand("adminstats", "Admin dashboard"),
            BotCommand("setlot", "Set MT5 lot size"),
            BotCommand("setmaxtrades", "Set max MT5 open trades"),
            BotCommand("mt5link", "Enable MT5 EA"),
            BotCommand("mt5status", "MT5 EA status"),
            BotCommand("mt5off", "Disable MT5 auto orders"),
            BotCommand("broadcast", "Admin broadcast message"),
            BotCommand("givepremium", "Admin activate premium manually"),
        ]
        if mt5queue:
            commands.append(BotCommand("mt5queue", "View MT5 queue"))
        if clearmt5:
            commands.append(BotCommand("clearmt5", "Clear MT5 queue"))

        loop.run_until_complete(telegram_app.bot.set_my_commands(commands))
        menu_status = "Telegram command menu added successfully"
    except Exception as e:
        logger.warning("set_my_commands failed: %s", e)
        menu_status = f"Webhook set, but command menu update failed: {e}"

    return jsonify({"webhook": response.json(), "menu": menu_status})


@app.get("/delete_webhook")
def delete_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    response = requests.post(url, timeout=20)
    return jsonify(response.json())


@app.get("/check_news")
def check_news():
    if CRON_SECRET and request.args.get("secret") != CRON_SECRET:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    try:
        fake_context = type("FakeContext", (), {"bot": telegram_app.bot})()
        loop.run_until_complete(scheduled_news_check(fake_context))
        loop.run_until_complete(maintenance_check(fake_context))
        return jsonify({"ok": True, "message": "News + VIP maintenance completed"})
    except Exception as e:
        logger.exception("Cron check error")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/mt5_orders")
def mt5_orders():
    """MT5 EA pulls queued orders using ?code=EA_CODE."""
    code = request.args.get("code", "").strip()
    if not code:
        return jsonify({"ok": False, "error": "Missing EA code"}), 400

    # Mark EA as connected every time it pulls orders.
    users = bot_module.load_json(bot_module.MT5_USERS_FILE, {})
    matched_user = None
    for uid, profile in users.items():
        if profile.get("bridge_code") == code:
            profile["enabled"] = True
            profile["last_seen_at"] = bot_module.now_utc().isoformat()
            profile.setdefault("lot_size", 0.01)
            profile.setdefault("max_active_orders", bot_module.MAX_ACTIVE_MT5_ORDERS)
            users[uid] = profile
            matched_user = uid
            break
    if matched_user:
        bot_module.save_json(bot_module.MT5_USERS_FILE, users)

    orders = bot_module.load_json(bot_module.MT5_ORDERS_FILE, [])
    pending = [
        o for o in orders
        if o.get("bridge_code") == code and o.get("status") == "PENDING_TO_BRIDGE"
    ]
    return jsonify({"ok": True, "connected": bool(matched_user), "orders": pending[:10]})


@app.post("/mt5_heartbeat")
def mt5_heartbeat():
    """EA calls this every 30-60 seconds to keep connection status live."""
    data = request.get_json(force=True, silent=True) or {}
    code = str(data.get("code") or request.args.get("code", "")).strip()
    if not code:
        return jsonify({"ok": False, "error": "Missing EA code"}), 400

    users = bot_module.load_json(bot_module.MT5_USERS_FILE, {})
    for uid, profile in users.items():
        if profile.get("bridge_code") == code:
            profile["enabled"] = True
            profile["last_seen_at"] = bot_module.now_utc().isoformat()
            profile["account"] = data.get("account", profile.get("account"))
            profile["broker"] = data.get("broker", profile.get("broker"))
            profile["terminal_connected"] = bool(data.get("terminal_connected", True))
            profile["updated_at"] = bot_module.now_utc().isoformat()
            users[uid] = profile
            bot_module.save_json(bot_module.MT5_USERS_FILE, users)
            return jsonify({"ok": True, "message": "EA heartbeat saved"})

    return jsonify({"ok": False, "error": "Invalid EA code"}), 404


def _parse_mt5_status_payload():
    """
    MT5 WebRequest sometimes sends malformed JSON with an extra trailing NULL.
    This parser logs raw data and recovers the first valid JSON object.
    """
    raw = request.get_data(as_text=True) or ""
    logger.info("MT5 STATUS RAW: %r", raw)

    data = request.get_json(force=True, silent=True)
    if isinstance(data, dict):
        return data, raw, None

    cleaned = raw.strip().replace("\x00", "")
    if not cleaned:
        return None, raw, "Empty request body"

    try:
        return json.loads(cleaned), raw, None
    except Exception:
        pass

    start = cleaned.find("{")
    end = cleaned.find("}", start)
    if start >= 0 and end > start:
        candidate = cleaned[start:end + 1]
        try:
            return json.loads(candidate), raw, None
        except Exception as e:
            return None, raw, f"Invalid JSON after recovery: {e}"

    return None, raw, "Invalid JSON body"


@app.post("/mt5_order_status")
def mt5_order_status():
    """MT5 EA reports order status after placing/skipping/failing."""
    try:
        data, raw, parse_error = _parse_mt5_status_payload()
        if not data:
            logger.warning("MT5 status payload invalid: %s raw=%r", parse_error, raw)
            return jsonify({"ok": False, "error": parse_error, "raw": raw}), 400

        code = str(data.get("code", "")).strip()
        order_id = str(data.get("order_id", "")).strip()
        status = str(data.get("status", "")).strip().upper()
        ticket = data.get("ticket")
        error = data.get("error") or data.get("err") or ""

        if not code or not order_id or not status:
            return jsonify({
                "ok": False,
                "error": "code, order_id and status are required",
                "received": data,
            }), 400

        orders = bot_module.load_json(bot_module.MT5_ORDERS_FILE, [])
        updated = False
        for order in orders:
            if order.get("bridge_code") == code and order.get("order_id") == order_id:
                order["status"] = status
                order["mt5_ticket"] = ticket
                order["error"] = error
                order["updated_at"] = bot_module.now_utc().isoformat()
                updated = True
                break

        bot_module.save_json(bot_module.MT5_ORDERS_FILE, orders)
        logger.info(
            "MT5 order status updated=%s order_id=%s status=%s ticket=%s error=%s",
            updated, order_id, status, ticket, error,
        )

        return jsonify({"ok": True, "updated": updated})
    except Exception as e:
        logger.exception("MT5 status update error")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/mpesa_callback")
def mpesa_callback():
    try:
        data = request.get_json(force=True)
        result = loop.run_until_complete(handle_mpesa_callback(data, telegram_app.bot))
        return jsonify(result)
    except Exception as e:
        logger.exception("M-Pesa callback error")
        return jsonify({"ok": False, "error": str(e)}), 500
