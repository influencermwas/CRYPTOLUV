import os
import threading
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()

from tg_sender import send_group
from scanner import scan_loop, scan_once
from scheduler import midnight_loop
from news_report import daily_market_report
from trade_manager import active_trades, daily_stats
from config import BOT_TOKEN, GROUP_CHAT_ID, ADMIN_ID

app = Flask(__name__)

started = False

@app.route("/")
def home():
    return {
        "status": "running",
        "bot": "MEXC Futures Scalping Signal Bot",
        "group_chat_id_set": bool(GROUP_CHAT_ID),
        "bot_token_set": bool(BOT_TOKEN),
        "active_trades": len(active_trades),
    }

@app.route("/health")
def health():
    return "OK"

@app.route("/admin/summary")
def admin_summary():
    key = request.args.get("key", "")
    if ADMIN_ID and key != ADMIN_ID:
        return {"error": "unauthorized"}, 401
    return {"active_trades": list(active_trades.keys()), "daily_stats": daily_stats}

@app.route("/admin/test")
def admin_test():
    key = request.args.get("key", "")
    if ADMIN_ID and key != ADMIN_ID:
        return {"error": "unauthorized"}, 401
    ok = send_group("✅ <b>Bot test message</b>\nMEXC futures scalping bot is connected.")
    return {"sent": ok}

@app.route("/admin/scan")
def admin_scan():
    key = request.args.get("key", "")
    if ADMIN_ID and key != ADMIN_ID:
        return {"error": "unauthorized"}, 401
    scan_once()
    return {"scan": "completed"}

@app.route("/admin/report")
def admin_report():
    key = request.args.get("key", "")
    if ADMIN_ID and key != ADMIN_ID:
        return {"error": "unauthorized"}, 401
    daily_market_report()
    return {"report": "sent"}

def start_background_threads():
    global started
    if started:
        return
    started = True
    threading.Thread(target=scan_loop, daemon=True).start()
    threading.Thread(target=midnight_loop, daemon=True).start()
    print("Background scanner and scheduler started.")

start_background_threads()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
