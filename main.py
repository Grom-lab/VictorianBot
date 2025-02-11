import os
import logging
import requests
from dotenv import load_dotenv
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Загрузка переменных окружения из файла .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)
YANDEX_API_KEY = os.environ.get("YANDEX_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
YANDEX_API_URL = "https://api.rasp.yandex.net/v3.0/search/"

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Привет! Я могу показать расписание электричек.\n' +
        'Для получения информации напишите команду в формате: \n' +
        '/raspisanie <откуда> <куда> <дата в формате ГГГГ-ММ-ДД>.\n' +
        'Например: /raspisanie Москва Тверь 2025-02-11.'
    )

# Получение расписания
async def get_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Проверяем количество аргументов
        if len(context.args) != 3:
            await update.message.reply_text("Пожалуйста, укажите корректные параметры: /raspisanie <откуда> <куда> <дата>.")
            return

        from_station, to_station, date = context.args
        
        params = {
            "apikey": YANDEX_API_KEY,
            "from": from_station,
            "to": to_station,
            "date": date,
            "transport_types": "suburban",
            "format": "json"
        }

        response = requests.get(YANDEX_API_URL, params=params)
        response.raise_for_status()

        data = response.json()
        segments = data.get("segments", [])

        if not segments:
            await update.message.reply_text("Не удалось найти электрички по вашему запросу.")
            return

        result = "Расписание электричек:\n"
        for segment in segments[:5]:  # Ограничиваем количество выводимых поездов
            departure = segment.get("departure", "Неизвестно")
            arrival = segment.get("arrival", "Неизвестно")
            duration = segment.get("duration", 0) // 60
            train_number = segment.get("thread", {}).get("number", "N/A")

            result += (f"\nПоезд {train_number}:\n"
                       f"Отправление: {departure}\n"
                       f"Прибытие: {arrival}\n"
                       f"Длительность: {duration} минут\n")

        await update.message.reply_text(result)

    except requests.RequestException as e:
        logger.error(f"Ошибка при запросе к API: {e}")
        await update.message.reply_text("Произошла ошибка при запросе к сервису расписаний.")
    except Exception as e:
        logger.error(f"Ошибка обработки команды: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте снова.")

# Основная функция
def main():
    # Инициализация бота
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Добавление обработчиков
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('raspisanie', get_schedule))

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
