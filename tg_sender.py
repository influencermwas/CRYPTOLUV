import requests
from config import BOT_TOKEN, GROUP_CHAT_ID

def send_group(text: str) -> bool:
    if not BOT_TOKEN:
        print("BOT_TOKEN is missing")
        return False

    if not GROUP_CHAT_ID:
        print("GROUP_CHAT_ID is missing")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": GROUP_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        r = requests.post(url, json=payload, timeout=20)
        if not r.ok:
            print("Telegram API error:", r.status_code, r.text)
            return False
        return True
    except Exception as e:
        print("Telegram send error:", e)
        return False
