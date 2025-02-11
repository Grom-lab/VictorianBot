import os
import logging
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Загрузка переменных окружения из файла .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Команда /start с меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🌤 Погода", callback_data="weather")],
        [InlineKeyboardButton("📰 Новости", callback_data="news")],
        [InlineKeyboardButton("💰 Криптовалюта", callback_data="crypto")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

# Обработчик кнопок меню
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "weather":
        await query.message.reply_text("Введите город: /weather <город>")
    elif query.data == "news":
        await news(query.message, context)
    elif query.data == "joke":
        await joke(query.message, context)
    elif query.data == "crypto":
        await crypto(query.message, context)
    elif query.data == "nasa":
        await nasa_apod(query.message, context)

# Команда /weather
async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = " ".join(context.args)
    if not city:
        await update.message.reply_text("Пожалуйста, укажите город: /weather <город>")
        return

    api_key = os.getenv("OPENWEATHERMAP_API_KEY")
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        temp = data["main"]["temp"]
        weather_desc = data["weather"][0]["description"]
        await update.message.reply_text(f"Погода в {city}: {weather_desc}, {temp}°C")
    else:
        await update.message.reply_text("Не удалось получить данные о погоде.")

# Команда /news
async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    api_key = os.getenv("NEWS_API_KEY")
    url = f"https://newsapi.org/v2/top-headlines?country=ru&apiKey={api_key}"
    response = requests.get(url)

    if response.status_code == 200:
        articles = response.json()["articles"][:5]  # Ограничиваем 5 новостями
        for article in articles:
            await update.message.reply_text(f"{article['title']}\n{article['url']}")
    else:
        await update.message.reply_text("Не удалось получить новости.")

# Команда /joke
async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = requests.get("https://v2.jokeapi.dev/joke/Any?lang=ru")
    if response.status_code == 200:
        joke_data = response.json()
        if joke_data["type"] == "single":
            await update.message.reply_text(joke_data["joke"])
        else:
            await update.message.reply_text(f"{joke_data['setup']}\n{joke_data['delivery']}")
    else:
        await update.message.reply_text("Не удалось получить шутку.")

# Команда /crypto
async def crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    coin = "bitcoin"
    response = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd")
    if response.status_code == 200:
        price = response.json()[coin]["usd"]
        await update.message.reply_text(f"Цена Bitcoin: ${price}")
    else:
        await update.message.reply_text("Не удалось получить данные о криптовалюте.")

# Команда /nasa
async def nasa_apod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    api_key = os.getenv("NASA_API_KEY")
    response = requests.get(f"https://api.nasa.gov/planetary/apod?api_key={api_key}")
    if response.status_code == 200:
        await update.message.reply_photo(response.json()["url"])
    else:
        await update.message.reply_text("Не удалось получить изображение дня от NASA.")

# Основная функция
def main():
    # Инициализация бота
    application = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    # Добавление обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("weather", weather))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Запуск бота
    application.run_polling()

if __name__ == "__main__":
    main()
