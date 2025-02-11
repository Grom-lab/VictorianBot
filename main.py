import os
import logging
from dotenv import load_dotenv
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import google.generativeai as genai

# Загрузка переменных окружения из файла .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Конфигурация API ключа и модели
YA_API_KEY = "70b19017-6fd8-4250-95c6-fa332c708d0e"
YA_BASE_URL = "https://api.rasp.yandex.net/v3.0/schedule/"

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
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

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Я ваш виртуальный ассистент. Введите название станции, чтобы узнать расписание автобусов.')

# Функция для получения расписания автобусов
async def get_schedule(station_code: str) -> str:
    params = {
        'apikey': YA_API_KEY,
        'station': station_code,
        'transport_types': 'bus',
        'date': '2025-02-11'
    }
    try:
        response = requests.get(YA_BASE_URL, params=params)
        response.raise_for_status()
        schedule_data = response.json()

        if 'schedule' not in schedule_data:
            return 'Не удалось получить расписание для указанной станции.'

        bus_schedule = []
        for item in schedule_data['schedule'][:5]:  # Ограничиваем вывод до 5 записей
            departure = item.get('departure', 'Неизвестно')
            direction = item.get('thread', {}).get('title', 'Неизвестное направление')
            bus_schedule.append(f"Отправление: {departure}, Направление: {direction}")

        return "\n".join(bus_schedule) if bus_schedule else 'Нет данных о расписании.'

    except requests.RequestException as e:
        logger.error(f"Ошибка при запросе к API Яндекса: {e}")
        return 'Произошла ошибка при получении данных расписания.'

# Обработчик текстовых сообщений для получения расписания
async def handle_schedule_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    station_code = update.message.text.strip()

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)

    # Получаем данные расписания и отправляем пользователю
    schedule_info = await get_schedule(station_code)
    await update.message.reply_text(schedule_info)

# Основная функция
def main():
    # Инициализация бота
    application = ApplicationBuilder().token(os.environ.get("TELEGRAM_BOT_TOKEN")).build()

    # Добавление обработчиков
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_schedule_request))

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
