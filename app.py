import os
import asyncio
import logging

import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from bot import (
    BOT_TOKEN,
    ADMIN_ID,
    start,
    analyze,
    news_command,
    broadcast,
    button_click,
    scheduled_news_check,
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
telegram_app.add_handler(CallbackQueryHandler(button_click))

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(telegram_app.initialize())
loop.run_until_complete(telegram_app.start())

app = Flask(__name__)


@app.get("/")
def home():
    return "Market Signal Bot Webhook is running ✅"


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
    return jsonify(response.json())


@app.get("/delete_webhook")
def delete_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    response = requests.post(url, timeout=20)
    return jsonify(response.json())


@app.get("/check_news")
def check_news():
    # Use this endpoint with UptimeRobot/Cron-job.org to trigger news broadcasts.
    # If CRON_SECRET is set, open /check_news?secret=YOUR_SECRET
    if CRON_SECRET and request.args.get("secret") != CRON_SECRET:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    try:
        fake_context = type("FakeContext", (), {"bot": telegram_app.bot})()
        loop.run_until_complete(scheduled_news_check(fake_context))
        return jsonify({"ok": True, "message": "News check completed"})
    except Exception as e:
        logger.exception("News check error")
        return jsonify({"ok": False, "error": str(e)}), 500
