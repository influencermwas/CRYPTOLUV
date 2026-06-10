import time
from mexc import get_last_price
from tg_sender import send_group
from analysis_engine import fmt_price
from config import LEVERAGE

active_trades = {}

daily_stats = {
    "signals": 0,
    "wins": 0,
    "losses": 0,
    "a": 0,
    "aplus": 0,
    "tp1": 0,
    "tp2": 0,
    "tp3": 0,
}

def format_signal(signal: dict):
    symbol = signal["symbol"].replace("_", "")
    reasons = "\n".join([f"✅ {r}" for r in signal["reasons"]])

    return f"""
🚀 <b>{symbol} FUTURES SCALP</b>

<b>Type:</b> {signal['direction']}
<b>Leverage:</b> {LEVERAGE}x

<b>Entry Zone:</b>
{fmt_price(signal['entry_low'])} - {fmt_price(signal['entry_high'])}

<b>Stop Loss:</b>
{fmt_price(signal['sl'])}

🎯 <b>Take Profits:</b>
TP1: {fmt_price(signal['tp1'])}
TP2: {fmt_price(signal['tp2'])}
TP3: {fmt_price(signal['tp3'])}

<b>Analysis:</b>
{reasons}

<b>Confidence:</b> {signal['confidence']}%
<b>Grade:</b> {signal['grade']}

⚠️ <b>Risk:</b> Futures trading is risky. Use proper margin and risk management.
""".strip()

def add_trade(signal: dict):
    active_trades[signal["symbol"]] = {
        **signal,
        "tp1_hit": False,
        "tp2_hit": False,
        "tp3_hit": False,
        "opened_at": time.time(),
    }
    daily_stats["signals"] += 1
    if signal["grade"] == "A SIGNAL":
        daily_stats["a"] += 1
    else:
        daily_stats["aplus"] += 1

def send_signal(signal: dict):
    sent = send_group(format_signal(signal))
    if sent:
        add_trade(signal)

def check_trade_updates():
    for symbol, trade in list(active_trades.items()):
        try:
            price = get_last_price(symbol)
        except Exception as e:
            print("Price check error:", symbol, e)
            continue

        if price is None:
            continue

        direction = trade["direction"]
        if direction == "LONG":
            tp1_hit = price >= trade["tp1"]
            tp2_hit = price >= trade["tp2"]
            tp3_hit = price >= trade["tp3"]
            sl_hit = price <= trade["sl"]
        else:
            tp1_hit = price <= trade["tp1"]
            tp2_hit = price <= trade["tp2"]
            tp3_hit = price <= trade["tp3"]
            sl_hit = price >= trade["sl"]

        clean_symbol = symbol.replace("_", "")

        if tp1_hit and not trade["tp1_hit"]:
            trade["tp1_hit"] = True
            daily_stats["tp1"] += 1
            send_group(f"✅ <b>{clean_symbol} TP1 HIT</b>\nCurrent Price: {fmt_price(price)}\nMove SL to break-even.")

        if tp2_hit and not trade["tp2_hit"]:
            trade["tp2_hit"] = True
            daily_stats["tp2"] += 1
            send_group(f"✅ <b>{clean_symbol} TP2 HIT</b>\nCurrent Price: {fmt_price(price)}")

        if tp3_hit and not trade["tp3_hit"]:
            trade["tp3_hit"] = True
            daily_stats["tp3"] += 1
            daily_stats["wins"] += 1
            send_group(f"🏆 <b>{clean_symbol} TP3 HIT</b>\nTrade completed.\nCurrent Price: {fmt_price(price)}")
            active_trades.pop(symbol, None)
            continue

        if sl_hit:
            daily_stats["losses"] += 1
            send_group(f"❌ <b>{clean_symbol} STOP LOSS HIT</b>\nCurrent Price: {fmt_price(price)}")
            active_trades.pop(symbol, None)

def reset_daily_stats():
    daily_stats.update({
        "signals": 0,
        "wins": 0,
        "losses": 0,
        "a": 0,
        "aplus": 0,
        "tp1": 0,
        "tp2": 0,
        "tp3": 0,
    })
