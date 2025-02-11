import os
import logging
from dotenv import load_dotenv
from telegram import Update, constants, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import google.generativeai as genai
import requests  # Для запросов к WeatherAPI

# Загрузка переменных окружения из файла .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Конфигурация API ключей
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")  # Добавляем ключ WeatherAPI

# Проверка наличия ключа WeatherAPI
if not WEATHER_API_KEY:
    logger.error("Ключ WEATHER_API_KEY не найден в переменных окружения!")

# Конфигурация Gemini API
genai.configure(api_key=GEMINI_API_KEY)
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

# Создание сессии чата Gemini
chat_session = model.start_chat(history=[])


# --- Weather Functionality ---

WEATHER_CITY = 0  # Состояние для ожидания ввода города

async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает диалог для получения погоды."""
    await update.message.reply_text(
        "Введите название города, для которого вы хотите узнать погоду:",
        reply_markup=ReplyKeyboardRemove()
    )
    return WEATHER_CITY

async def get_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает погоду для указанного города и отправляет ответ."""
    city = update.message.text
    if not WEATHER_API_KEY:
        await update.message.reply_text("Ошибка: API ключ WeatherAPI не настроен.")
        return ConversationHandler.END

    try:
        url = f"http://api.weatherapi.com/v1/current.json?key={WEATHER_API_KEY}&q={city}&aqi=no"
        response = requests.get(url)
        response.raise_for_status()  # Проверка на ошибки HTTP
        data = response.json()

        # Извлекаем данные о погоде
        city_name = data["location"]["name"]
        country = data["location"]["country"]
        temperature_celsius = data["current"]["temp_c"]
        condition_text = data["current"]["condition"]["text"]
        wind_kph = data["current"]["wind_kph"]
        humidity = data["current"]["humidity"]

        weather_message = (
            f"Погода в городе {city_name}, {country}:\n"
            f"Температура: {temperature_celsius}°C\n"
            f"Состояние: {condition_text}\n"
            f"Ветер: {wind_kph} км/ч\n"
            f"Влажность: {humidity}%"
        )
        await update.message.reply_text(weather_message)

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к WeatherAPI: {e}")
        await update.message.reply_text("Произошла ошибка при получении погоды. Пожалуйста, попробуйте позже.")
    except KeyError as e:
        logger.error(f"Ошибка при разборе ответа WeatherAPI: {e}")
        await update.message.reply_text("Не удалось найти информацию о погоде для этого города. Пожалуйста, проверьте название города.")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}")
        await update.message.reply_text("Произошла непредвиденная ошибка.")

    return ConversationHandler.END

async def cancel_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет операцию получения погоды."""
    await update.message.reply_text("Операция получения погоды отменена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END



# --- Gemini Functionality ---

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Я ваш виртуальный ассистент. Чем могу помочь?')

# Обработчик текстовых сообщений
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text

    # Показываем, что бот печатает
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)

    try:
        response = chat_session.send_message(user_input)

        # Разделение длинного сообщения на части
        max_length = 4096
        if len(response.text) > max_length:
            for i in range(0, len(response.text), max_length):
                part = response.text[i:i + max_length]
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}")
        await update.message.reply_text("Произошла ошибка при обработке вашего запроса. Попробуйте снова.")



# --- Main Function ---

def main():
    # Инициализация бота
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # --- Weather Conversation Handler ---
    weather_handler = ConversationHandler(
        entry_points=[CommandHandler('weather', weather)],
        states={
            WEATHER_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weather)],
        },
        fallbacks=[CommandHandler('cancel', cancel_weather)],
    )
    application.add_handler(weather_handler)

    # Добавление обработчиков Gemini
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo))

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
