import os
import logging
import requests
from dotenv import load_dotenv
from telegram import Update, constants
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
import google.generativeai as genai

# Загрузка переменных окружения из файла .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы для ConversationHandler
WEATHER_CITY = 1

# Конфигурация Gemini
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 65536,
    "response_mime_type": "text/plain",
}
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-thinking-exp-01-21",
    generation_config=generation_config,
)
chat_session = model.start_chat(history=[])

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Я ваш виртуальный ассистент. Чем могу помочь?')

# Обработчик текстовых сообщений
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, 
        action=constants.ChatAction.TYPING
    )
    
    try:
        response = chat_session.send_message(update.message.text)
        if len(response.text) > 4096:
            for part in [response.text[i:i+4096] for i in range(0, len(response.text), 4096)]:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Ошибка Gemini: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")

# Функции для работы с погодой
async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск диалога запроса погоды"""
    await update.message.reply_text(
        "Введите название города для получения погоды:"
    )
    return WEATHER_CITY

async def handle_weather_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенного города"""
    city = update.message.text
    try:
        weather_info = get_weather_data(city)
        await update.message.reply_text(weather_info)
    except Exception as e:
        logger.error(f"Ошибка погоды: {e}")
        await update.message.reply_text("Не удалось получить данные о погоде. Попробуйте еще раз.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена диалога"""
    await update.message.reply_text("Запрос погоды отменен.")
    return ConversationHandler.END

def get_weather_data(city: str) -> str:
    """Запрос данных о погоде через API"""
    api_key = os.environ["WEATHER_API_KEY"]
    url = f"http://api.weatherapi.com/v1/current.json?key={api_key}&q={city}&lang=ru"
    
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    
    location = data["location"]
    current = data["current"]
    
    return (
        f"🌤 Погода в {location['name']}, {location['country']}:\n\n"
        f"🌡 Температура: {current['temp_c']}°C\n"
        f"💨 Ощущается как: {current['feelslike_c']}°C\n"
        f"📝 Условия: {current['condition']['text']}\n"
        f"🌪 Ветер: {current['wind_kph']} км/ч ({current['wind_dir']})\n"
        f"💧 Влажность: {current['humidity']}%"
    )

def main():
    application = ApplicationBuilder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()

    # Добавляем обработчики
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("weather", weather_command)],
        states={
            WEATHER_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_weather_city)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    application.run_polling()

if __name__ == '__main__':
    main()
