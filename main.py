import os
import logging
from dotenv import load_dotenv
from telegram import Update, constants, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import requests
import google.generativeai as genai

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация API ключей
YA_API_KEY = os.environ.get("YA_API_KEY")  # Получаем из .env
YA_BASE_URL = "https://api.weather.yandex.ru/v2/forecast"  # URL для погоды
YA_GEO_URL = "https://geocode-maps.yandex.ru/1.x/"      # URL for Geocoding

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 65536,
    "response_mime_type": "text/plain",
}
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-thinking-exp-01-21",  # Or your preferred model
    generation_config=generation_config,
)
chat_session = model.start_chat(history=[])



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Узнать погоду", callback_data='get_weather')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        'Привет! Я ваш виртуальный ассистент.  Нажмите кнопку, чтобы узнать погоду.',
        reply_markup=reply_markup
    )



async def get_weather_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the button press for getting weather."""
    query = update.callback_query
    await query.answer()  # Acknowledge the button press
    await query.edit_message_text(text="Пожалуйста, отправьте мне название города или геолокацию.")



async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles location messages to get weather."""
    user_location = update.message.location
    latitude = user_location.latitude
    longitude = user_location.longitude

    weather_info = await get_weather(latitude, longitude)
    await update.message.reply_text(weather_info)



async def handle_city_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles city name messages to get weather using geocoding."""
    city_name = update.message.text.strip()

    try:
        # Geocode the city name to get coordinates
        geo_params = {
            "apikey": os.environ.get("YA_GEO_API_KEY"),  # Use a separate Geocoding API key
            "geocode": city_name,
            "format": "json",
        }
        geo_response = requests.get(YA_GEO_URL, params=geo_params)
        geo_response.raise_for_status()
        geo_data = geo_response.json()
        # print(geo_data)


        if geo_data["response"]["GeoObjectCollection"]["featureMember"]:

            point = geo_data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["Point"]["pos"]
            longitude, latitude = map(float, point.split(" "))

            weather_info = await get_weather(latitude, longitude)
            await update.message.reply_text(weather_info)
        else:
            await update.message.reply_text("Не удалось найти координаты для указанного города.")


    except requests.RequestException as e:
        logger.error(f"Ошибка при запросе к геокодеру: {e}")
        await update.message.reply_text("Произошла ошибка при определении местоположения.")
    except (KeyError, IndexError, ValueError) as e:
        logger.error(f"Ошибка при обработке ответа геокодера: {e}")
        await update.message.reply_text("Произошла ошибка при обработке ответа геокодера.")




async def get_weather(latitude: float, longitude: float) -> str:
    """Fetches weather data from Yandex.Weather API."""
    params = {
        'lat': latitude,
        'lon': longitude,
        'lang': 'ru_RU',  # Request results in Russian
        'limit': 1,      # Get only the current weather
        'hours': 'false',  # exclude hourly forecast
        'extra': 'false'
    }
    headers = {'X-Yandex-API-Key': YA_API_KEY}

    try:
        response = requests.get(YA_BASE_URL, params=params, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        weather_data = response.json()
        # print(weather_data)

        # Extract relevant weather information
        fact = weather_data['fact']
        temp = fact['temp']
        feels_like = fact['feels_like']
        condition = fact['condition']
        wind_speed = fact['wind_speed']

       # Translate the condition.  Could use a dictionary for more complete translations.
        condition_translations = {
            "clear": "ясно",
            "partly-cloudy": "малооблачно",
            "cloudy": "облачно с прояснениями",
            "overcast": "пасмурно",
            "drizzle": "морось",
            "light-rain": "небольшой дождь",
            "rain": "дождь",
            "moderate-rain": "умеренно сильный дождь",
            "heavy-rain": "сильный дождь",
            "continuous-heavy-rain": "длительный сильный дождь",
            "showers": "ливень",
            "wet-snow": "дождь со снегом",
            "light-snow": "небольшой снег",
            "snow": "снег",
            "snow-showers": "снегопад",
            "hail": "град",
            "thunderstorm": "гроза",
            "thunderstorm-with-rain": "дождь с грозой",
            "thunderstorm-with-hail": "гроза с градом",
        }
        condition_translated = condition_translations.get(condition, condition)  # Fallback to original if not found


        weather_report = (
            f"Температура: {temp}°C\n"
            f"Ощущается как: {feels_like}°C\n"
            f"Состояние: {condition_translated}\n"
            f"Скорость ветра: {wind_speed} м/с"
        )
        return weather_report


    except requests.RequestException as e:
        logger.error(f"Ошибка при запросе к API погоды: {e}")
        return 'Произошла ошибка при получении данных о погоде.'
    except KeyError as e:
        logger.error(f"Ошибка при обработке данных погоды: {e}.  Ответ: {weather_data}")
        return "Произошла ошибка при обработке данных о погоде: неверный формат ответа."



def main():
    application = ApplicationBuilder().token(os.environ.get("TELEGRAM_BOT_TOKEN")).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(get_weather_button, pattern='^get_weather$'))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_city_name)) # Handle city names

    application.run_polling()

if __name__ == '__main__':
    main()
