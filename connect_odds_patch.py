from pathlib import Path

bot_path = Path("bot.py")
app_path = Path("app.py")

if not bot_path.exists():
    raise SystemExit("❌ bot.py not found. Run this inside CRYPTOLUV folder.")

bot = bot_path.read_text(encoding="utf-8")

# 1) Import odds.py safely
if "import odds as odds_module" not in bot:
    marker = "from telegram.ext import (\n"
    if marker not in bot:
        raise SystemExit("❌ Could not find telegram.ext import block in bot.py")
    bot = bot.replace(marker, "import odds as odds_module\n" + marker, 1)

# 2) Add Premium Odds button in main_menu
premium_button = '        [InlineKeyboardButton("💎 Premium Signals", callback_data="premium")],\n'
odds_button = '        [InlineKeyboardButton("⚽ Get Premium Odds", callback_data="premium_odds")],\n'
if odds_button not in bot:
    if premium_button not in bot:
        raise SystemExit("❌ Could not find Premium Signals button in bot.py")
    bot = bot.replace(premium_button, premium_button + odds_button, 1)

# 3) Add callback handling inside button_click
old = '''    elif data == "premium":
        await show_premium(query.message.chat_id, query.from_user.id, context)
    elif data.startswith("payplan_"):
'''
new = '''    elif data == "premium":
        await show_premium(query.message.chat_id, query.from_user.id, context)
    elif data == "premium_odds":
        await odds_module.show_premium_odds_menu(query.message.chat_id, query.from_user.id, context)
    elif data.startswith("odds_league_"):
        league_id = data.replace("odds_league_", "")
        await odds_module.send_premium_odds_for_league(query.message.chat_id, query.from_user.id, context, league_id)
    elif data.startswith("payplan_"):
'''
if 'data == "premium_odds"' not in bot:
    if old not in bot:
        raise SystemExit("❌ Could not find premium callback block in bot.py")
    bot = bot.replace(old, new, 1)

# 4) Add /odds command in bot.py polling main
odds_command_line = '    app.add_handler(CommandHandler("odds", odds_module.odds_command))\n'
if odds_command_line not in bot:
    premium_command_line = '    app.add_handler(CommandHandler("premium", premium_command))\n'
    if premium_command_line in bot:
        bot = bot.replace(premium_command_line, premium_command_line + odds_command_line, 1)

bot_path.write_text(bot, encoding="utf-8")
print("✅ bot.py connected to odds.py")

# 5) Patch app.py webhook runner if present
if app_path.exists():
    app = app_path.read_text(encoding="utf-8")

    if "import odds as odds_module" not in app:
        marker = "from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters\n"
        if marker in app:
            app = app.replace(marker, marker + "import odds as odds_module\n", 1)
        else:
            app = app.replace("import bot as bot_module\n", "import bot as bot_module\nimport odds as odds_module\n", 1)

    if 'telegram_app.add_handler(CommandHandler("odds", odds_module.odds_command))' not in app:
        premium_line = 'telegram_app.add_handler(CommandHandler("premium", premium_command))\n'
        if premium_line in app:
            app = app.replace(
                premium_line,
                premium_line + 'telegram_app.add_handler(CommandHandler("odds", odds_module.odds_command))\n',
                1
            )

    if 'BotCommand("odds", "Premium football odds analysis")' not in app:
        command_line = '            BotCommand("premium", "Get premium VIP signals"),\n'
        if command_line in app:
            app = app.replace(
                command_line,
                command_line + '            BotCommand("odds", "Premium football odds analysis"),\n',
                1
            )

    app_path.write_text(app, encoding="utf-8")
    print("✅ app.py registered /odds")
else:
    print("ℹ️ app.py not found, skipped")

print("\\n✅ Done. Next run: python3 -m py_compile bot.py app.py odds.py")
