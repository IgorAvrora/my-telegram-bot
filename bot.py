from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ВСТАВЬТЕ СЮДА ВАШ ТОКЕН ОТ BOTFATHER
TOKEN = "8408104861:AAFY7m6_Ztbo9_lZKZB5LV7PWEP2W4OBv6E"

# Команда /start — приветствие
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я твой бот-путеводитель 🗺️\n\n"
        "Напиши /help чтобы узнать что я умею!"
    )

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Доступные команды:\n"
        "/start — Начать\n"
        "/help — Помощь\n"
        "/etretat — Рестораны Этрета\n"
        "/trouville — Рестораны Трувиля\n"
        "/chateaux — Замки Луары"
    )

# Команда /etretat
async def etretat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌊 Рестораны ЭТРЕТА (11 июля):\n\n"
        "⭐ Le Donjon (Domaine Saint-Clair)\n"
        "Адрес: Chemin de Saint-Clair\n"
        "Гастрономическая французская кухня\n"
        "Цена: €69–149/чел\n"
        "Бронь: thefork.fr\n\n"
        "⭐ Restaurant du Casino JOA\n"
        "Французская, вид на море\n"
        "Бронь: thefork.fr"
    )

# Команда /trouville
async def trouville(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏖️ Рестораны ТРУВИЛЯ:\n\n"
        "12 июля:\n"
        "⭐ Les Mouettes — 4.4/5 (2568 отзывов)\n"
        "Морепродукты, у воды\n\n"
        "13 июля:\n"
        "⭐ Le Noroit — 4.5/5 (1188 отзывов)\n"
        "Французская, морепродукты\n\n"
        "Бронь: thefork.fr"
    )

# Команда /chateaux
async def chateaux(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏰 ЗАМКИ ЛУАРЫ (15–16 июля):\n\n"
        "1. Шенонсо — ОБЯЗАТЕЛЬНО билет онлайн!\n"
        "   chenonceau.com\n\n"
        "2. Шамбор — рекомендуется онлайн\n"
        "   domaine-chambord.org\n\n"
        "3. Амбуаз + Кло-Люсе (гробница Да Винчи)\n\n"
        "4. Замок де Блуа\n\n"
        "💡 Комбо-билет: loirevalley-tickets.com"
    )

# Ответ на любое другое сообщение
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text(
        f"Вы написали: «{text}»\n\n"
        "Используйте /help чтобы увидеть все команды."
    )

# Запуск бота
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("etretat", etretat))
    app.add_handler(CommandHandler("trouville", trouville))
    app.add_handler(CommandHandler("chateaux", chateaux))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    print("Бот запущен! Нажмите Ctrl+C чтобы остановить.")
    app.run_polling()