import os
import asyncio
import logging

import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from bot import (
    BOT_TOKEN,
    start,
    analyze,
    news_command,
    broadcast,
    premium_command,
    givepremium,
    vip_history_command,
    vip_performance_command,
    button_click,
    text_handler,
    scheduled_news_check,
    maintenance_check,
    handle_mpesa_callback,
)

load_dotenv()

logger = logging.getLogger(__name__)

PUBLIC_URL = os.getenv("PUBLIC_URL", "").strip().rstrip("/")
CRON_SECRET = os.getenv("CRON_SECRET", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing. Add it in Render Environment Variables.")

telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("analyze", analyze))
telegram_app.add_handler(CommandHandler("news", news_command))
telegram_app.add_handler(CommandHandler("broadcast", broadcast))
telegram_app.add_handler(CommandHandler("premium", premium_command))
telegram_app.add_handler(CommandHandler("givepremium", givepremium))
telegram_app.add_handler(CommandHandler("viphistory", vip_history_command))
telegram_app.add_handler(CommandHandler("vipperformance", vip_performance_command))
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

    loop.run_until_complete(
        telegram_app.bot.set_my_commands([
            BotCommand("start", "Open main menu"),
            BotCommand("analyze", "Analyze crypto, forex or stock"),
            BotCommand("news", "Check market news alerts"),
            BotCommand("premium", "Get premium VIP signals"),
            BotCommand("viphistory", "View VIP signal history"),
            BotCommand("vipperformance", "View VIP win/loss performance"),
            BotCommand("broadcast", "Admin broadcast message"),
            BotCommand("givepremium", "Admin activate premium manually"),
        ])
    )

    return jsonify({
        "webhook": response.json(),
        "menu": "Telegram command menu added successfully"
    })


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


@app.post("/mpesa_callback")
def mpesa_callback():
    try:
        data = request.get_json(force=True)
        result = loop.run_until_complete(handle_mpesa_callback(data, telegram_app.bot))
        return jsonify(result)
    except Exception as e:
        logger.exception("M-Pesa callback error")
        return jsonify({"ok": False, "error": str(e)}), 500
