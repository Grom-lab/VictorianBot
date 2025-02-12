import os
import logging
from dotenv import load_dotenv
from telegram import Update, constants, ReplyKeyboardMarkup, ReplyKeyboardRemove
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

# Функция получения времени по городу
def get_time(city: str):
    url = f"http://worldtimeapi.org/api/timezone/Etc/UTC.txt"
    geo_url = f"http://worldtimeapi.org/api/timezone/{city.replace(' ', '_')}"
    response = requests.get(geo_url)

    if response.status_code != 200:
        return f"Не удалось получить информацию о времени для города {city}. Попробуйте другой город."

    data = response.json()
    time = data["datetime"]
    timezone = data["timezone"]

    return f"Текущее время в {city} ({timezone}): {time}"

# Функция для главного меню
def get_main_menu():
    return ReplyKeyboardMarkup([["/weather", "/time", "Выход"]], one_time_keyboard=True)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я ваш виртуальный ассистент. Чем могу помочь?\n\n"
        "Выберите одну из опций:",
        reply_markup=get_main_menu()
    )

# Команда /weather
async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Введите город после команды, например: /weather Москва")
        return

    city = " ".join(context.args)
    weather_info = get_weather(city)
    await update.message.reply_text(weather_info, reply_markup=get_main_menu())

# Команда /time
async def time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Введите город после команды, например: /time Москва")
        return

    city = " ".join(context.args)
    time_info = get_time(city)
    await update.message.reply_text(time_info, reply_markup=get_main_menu())

# Функция для выхода из меню
async def exit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "До свидания! Если захотите воспользоваться чем-то снова, просто напишите мне.",
        reply_markup=ReplyKeyboardRemove()
    )

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
    application.add_handler(CommandHandler("time", time))  # Обработчик команды /time
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo))

    # Добавление обработчика для кнопки "Выход"
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("Выход"), exit_menu))

    # Запуск бота
    application.run_polling()

if __name__ == "__main__":
    main()
    
