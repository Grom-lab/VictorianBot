import os
import logging
import requests
from dotenv import load_dotenv
from telegram import Update, constants, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
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

# News API Key
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "ae7160fcd4364ffdb51951b0187afa88")  # Замените на ваш API ключ

# --- News API functions ---
def get_news(category="general", country="ru"):
    """
    Получает последние новости из News API.

    Args:
        category: Категория новостей (например, business, entertainment, general, health, science, sports, technology).
        country: Страна, для которой нужно получить новости (например, us, ru, gb).

    Returns:
        Список новостей в формате словарей, или None, если произошла ошибка.
    """
    url = f"https://newsapi.org/v2/top-headlines?country={country}&category={category}&apiKey={NEWS_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        if data["status"] == "ok":
            return data["articles"]
        else:
            logger.error(f"News API error: {data['message']}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching news: {e}")
        return None

# --- Telegram Bot functions ---

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Новости", callback_data="news_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Привет! Я ваш виртуальный ассистент. Чем могу помочь? Выберите опцию:', reply_markup=reply_markup)

# Функция для отображения меню новостей
async def news_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Необходимо всегда вызывать answer() для CallbackQuery

    keyboard = [
        [InlineKeyboardButton("Общие", callback_data="news_general")],
        [InlineKeyboardButton("Бизнес", callback_data="news_business")],
        [InlineKeyboardButton("Спорт", callback_data="news_sports")],
        [InlineKeyboardButton("Технологии", callback_data="news_technology")],
        [InlineKeyboardButton("Назад", callback_data="start_menu")] # Кнопка "Назад"
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите категорию новостей:", reply_markup=reply_markup)


# Функция для отображения новостей выбранной категории
async def show_news(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    query = update.callback_query
    await query.answer()

    news_articles = get_news(category=category)

    if news_articles:
        message_text = ""
        for article in news_articles[:5]:  # Покажем только первые 5 новостей
            title = article.get("title", "Без заголовка")
            description = article.get("description", "Без описания")
            url = article.get("url", "")
            message_text += f"<b>{title}</b>\n{description}\n<a href='{url}'>Подробнее</a>\n\n"

        # Разделяем сообщение на части, если оно слишком длинное
        max_length = 4096
        if len(message_text) > max_length:
            for i in range(0, len(message_text), max_length):
                part = message_text[i:i + max_length]
                await context.bot.send_message(chat_id=query.message.chat_id, text=part, parse_mode=constants.ParseMode.HTML, disable_web_page_preview=True)
        else:
            await context.bot.send_message(chat_id=query.message.chat_id, text=message_text, parse_mode=constants.ParseMode.HTML, disable_web_page_preview=True)

    else:
        await query.edit_message_text("Не удалось получить новости.")

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

# Обработчик CallbackQuery
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "news_menu":
        await news_menu(update, context)
    elif query.data == "news_general":
        await show_news(update, context, category="general")
    elif query.data == "news_business":
        await show_news(update, context, category="business")
    elif query.data == "news_sports":
        await show_news(update, context, category="sports")
    elif query.data == "news_technology":
        await show_news(update, context, category="technology")
    elif query.data == "start_menu":  # Обработка кнопки "Назад"
        await start(update, context)
    else:
        await query.edit_message_text(f"Выбрана опция: {query.data}")



# Основная функция
def main():
    # Инициализация бота
    application = ApplicationBuilder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()

    # Добавление обработчиков
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button))  # Обработчик для кнопок
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo))

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
