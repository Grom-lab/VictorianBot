import os
import logging
from dotenv import load_dotenv
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
import requests

# Загрузка переменных окружения из файла .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Конфигурация API ключа и модели Gemini
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

# Создание сессии чата
chat_session = model.start_chat(history=[])

# Функция получения погоды
def get_weather(city: str):
    url = f"https://api.open-meteo.com/v1/forecast?latitude=0&longitude=0&current_weather=true"

    # Определение координат города через geocode API
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=ru"
    geo_response = requests.get(geo_url).json()

    if "results" not in geo_response or not geo_response["results"]:
        return "Не удалось найти город. Попробуйте другой запрос."

    latitude = geo_response["results"][0]["latitude"]
    longitude = geo_response["results"][0]["longitude"]
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current_weather=true"

    # Получение погоды
    response = requests.get(url).json()
    if "current_weather" not in response:
        return "Ошибка при получении данных о погоде."

    weather = response["current_weather"]
    temperature = weather["temperature"]
    wind_speed = weather["windspeed"]
    conditions = weather["weathercode"]

    # Простая интерпретация кода погоды
    weather_conditions = {
        0: "Ясно",
        1: "Преимущественно ясно",
        2: "Переменная облачность",
        3: "Пасмурно",
        45: "Туман",
        48: "Ледяной туман",
        51: "Легкий моросящий дождь",
        53: "Моросящий дождь",
        55: "Сильный моросящий дождь",
        61: "Легкий дождь",
        63: "Дождь",
        65: "Сильный дождь",
        71: "Легкий снегопад",
        73: "Снегопад",
        75: "Сильный снегопад",
        80: "Легкий ливень",
        81: "Ливень",
        82: "Сильный ливень",
    }
    
    weather_desc = weather_conditions.get(conditions, "Неизвестные погодные условия")

    return f"Погода в {city}:\n🌡 Температура: {temperature}°C\n💨 Ветер: {wind_speed} км/ч\n☁️ Условия: {weather_desc}"

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я ваш виртуальный ассистент. Чем могу помочь?\n\n"
                                    "Например, попробуйте /weather Москва")

# Команда /weather
async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Введите город после команды, например: /weather Москва")
        return

    city = " ".join(context.args)
    weather_info = get_weather(city)
    await update.message.reply_text(weather_info)

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

# Основная функция
def main():
    # Инициализация бота
    application = ApplicationBuilder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()

    # Добавление обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("weather", weather))  # Убираем pass_args
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo))

    # Запуск бота
    application.run_polling()

if __name__ == "__main__":
    main()
        
