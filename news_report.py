import feedparser
from mexc import get_tickers
from tg_sender import send_group
from trade_manager import daily_stats, reset_daily_stats
from config import NEWS_RSS

def get_change(item: dict):
    try:
        return float(item.get("riseFallRate", 0) or 0) * 100
    except Exception:
        return 0.0

def daily_market_report():
    try:
        tickers = get_tickers()
        usdt = [x for x in tickers if x.get("symbol", "").endswith("_USDT")]

        for x in usdt:
            x["change"] = get_change(x)

        gainers = sorted(usdt, key=lambda x: x["change"], reverse=True)[:10]
        losers = sorted(usdt, key=lambda x: x["change"])[:10]

        gainer_text = "\n".join([f"{i+1}. {x['symbol'].replace('_','')} +{x['change']:.2f}%" for i, x in enumerate(gainers)]) or "No data."
        loser_text = "\n".join([f"{i+1}. {x['symbol'].replace('_','')} {x['change']:.2f}%" for i, x in enumerate(losers)]) or "No data."

        feed = feedparser.parse(NEWS_RSS)
        news_items = feed.entries[:6]
        news_text = "\n".join([f"• {item.title}" for item in news_items]) or "No crypto news found."

        closed = daily_stats["wins"] + daily_stats["losses"]
        win_rate = (daily_stats["wins"] / closed * 100) if closed else 0

        text = f"""
🌙 <b>DAILY CRYPTO MARKET SUMMARY</b>

📈 <b>Top MEXC Futures Gainers</b>
{gainer_text}

📉 <b>Top MEXC Futures Losers</b>
{loser_text}

📰 <b>Crypto News</b>
{news_text}

📊 <b>Bot Performance</b>
Signals Today: {daily_stats['signals']}
TP1 Hits: {daily_stats['tp1']}
TP2 Hits: {daily_stats['tp2']}
TP3 Wins: {daily_stats['wins']}
SL Losses: {daily_stats['losses']}
Win Rate: {win_rate:.1f}%
A Signals: {daily_stats['a']}
A+ Signals: {daily_stats['aplus']}

⚠️ Trade safely. 10x leverage is high risk.
""".strip()

        send_group(text)
        reset_daily_stats()

    except Exception as e:
        print("Daily report error:", e)
