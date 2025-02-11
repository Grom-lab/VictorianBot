import os
import logging
import asyncio
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
import requests

# Загрузка переменных окружения
load_dotenv()

# Настройка логгера
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

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

# Токены
WEATHER_TOKEN = os.environ.get("WEATHER_TOKEN")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Состояния для ConversationHandler
WEATHER_LOCATION = 1


# Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я ваш виртуальный ассистент. Чем могу помочь?")


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите название города:")
    return WEATHER_LOCATION


async def fetch_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_location = update.message.text
    loop = asyncio.get_event_loop()
    
    try:
        # Прямой запрос к OpenWeatherMap API по названию города
        url = f"http://api.openweathermap.org/data/2.5/weather?q={user_location}&appid={WEATHER_TOKEN}&units=metric&lang=ru"
        response = await loop.run_in_executor(None, requests.get, url)
        
        if response.status_code != 200:
            await update.message.reply_text("Местоположение не найдено или произошла ошибка")
            return ConversationHandler.END

        # Парсинг ответа
        weather_data = response.json()
        description = weather_data["weather"][0]["description"]
        temperature = weather_data["main"]["temp"]
        humidity = weather_data["main"]["humidity"]
        wind_speed = weather_data["wind"]["speed"]
        
        # Формирование сообщения
        weather_message = (
            f"Погода в {user_location}:\n"
            f"Описание: {description.capitalize()}\n"
            f"Температура: {temperature}°C\n"
            f"Влажность: {humidity}%\n"
            f"Скорость ветра: {wind_speed} м/с"
        )
        await update.message.reply_text(weather_message)
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text("Произошла ошибка при обработке запроса")
    
    return ConversationHandler.END


# Обработчик для Gemini AI
async def gemini_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING
    )
    
    try:
        # Генерация ответа
        response = chat_session.send_message(user_input)
        
        # Разделение длинных сообщений
        max_length = 4096
        if len(response.text) > max_length:
            for i in range(0, len(response.text), max_length):
                await update.message.reply_text(response.text[i : i + max_length])
        else:
            await update.message.reply_text(response.text)
            
    except Exception as e:
        logger.error(f"Ошибка Gemini: {e}")
        await update.message.reply_text("Произошла ошибка при генерации ответа")


def main():
    # Создание приложения
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Добавление обработчиков
    application.add_handler(CommandHandler("start", start))
    
    # Обработчик для погоды
    weather_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("weather", weather_command)],
        states={
            WEATHER_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fetch_weather)
            ]
        },
        fallbacks=[],
    )
    application.add_handler(weather_conv_handler)
    
    # Основной обработчик сообщений
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, gemini_handler)
    )

    # Запуск бота
    application.run_polling()


if __name__ == "__main__":
    main()
