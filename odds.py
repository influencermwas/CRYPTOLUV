"""
odds.py

Standalone Premium Football Odds module for CRYPTOLUV.

This file is intentionally a scaffold module. It is designed to be imported
by bot.py without changing existing signal logic.

You will later connect:
- is_premium()
- premium_plan_keyboard()
- register_user()
- Telegram callback handlers
from your existing bot.

Environment variables:
    ODDS_API_KEY
    ODDS_REGIONS=uk,eu
    ODDS_MARKETS=h2h
"""

import os
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_REGIONS = os.getenv("ODDS_REGIONS", "uk,eu")
ODDS_MARKETS = os.getenv("ODDS_MARKETS", "h2h")

LEAGUES = {
    "epl": ("Premier League", "soccer_epl"),
    "laliga": ("LaLiga", "soccer_spain_la_liga"),
    "seriea": ("Italian Serie A", "soccer_italy_serie_a"),
    "bundesliga": ("Bundesliga", "soccer_germany_bundesliga"),
    "ligue1": ("French Ligue 1", "soccer_france_ligue_one"),
}


def odds_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏴 Premier League", callback_data="odds_league_epl")],
        [InlineKeyboardButton("🇪🇸 LaLiga", callback_data="odds_league_laliga")],
        [InlineKeyboardButton("🇮🇹 Italian Serie A", callback_data="odds_league_seriea")],
        [InlineKeyboardButton("🇩🇪 Bundesliga", callback_data="odds_league_bundesliga")],
        [InlineKeyboardButton("🇫🇷 French Ligue 1", callback_data="odds_league_ligue1")],
    ])


def fetch_odds(league_id: str):
    if league_id not in LEAGUES:
        raise ValueError("Unknown league")

    _, sport_key = LEAGUES[league_id]

    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"

    r = requests.get(
        url,
        params={
            "apiKey": ODDS_API_KEY,
            "regions": ODDS_REGIONS,
            "markets": ODDS_MARKETS,
            "oddsFormat": "decimal",
        },
        timeout=20,
    )

    r.raise_for_status()
    return r.json()


def analyse(events):
    results = []

    for event in events:
        if not event.get("bookmakers"):
            continue

        market = event["bookmakers"][0]["markets"][0]

        best = max(market["outcomes"], key=lambda x: 1 / float(x["price"]))

        confidence = round((1 / float(best["price"])) * 100)

        results.append({
            "match": f'{event["home_team"]} vs {event["away_team"]}',
            "pick": best["name"],
            "odds": best["price"],
            "confidence": confidence,
        })

    return sorted(results, key=lambda x: x["confidence"], reverse=True)


async def odds_command(update, context):
    await update.message.reply_text(
        "⚽ Premium Odds\n\nChoose a league.",
        reply_markup=odds_keyboard()
    )
