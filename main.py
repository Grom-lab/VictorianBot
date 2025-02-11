import os
import logging
from dotenv import load_dotenv
from telegram import Update, constants, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
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

# API ключ для NewsAPI
NEWS_API_KEY = os.environ["NEWS_API_KEY"]  # Убедитесь, что добавили переменную окружения NEWS_API_KEY

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Новости", callback_data='news')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Привет! Я ваш виртуальный ассистент. Чем могу помочь?', reply_markup=reply_markup)

# Обработчик для кнопок
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'news':
        await show_news_menu(update, context)

async def show_news_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("США", callback_data='news_us')],
        [InlineKeyboardButton("Россия", callback_data='news_ru')],
        [InlineKeyboardButton("Украина", callback_data='news_ua')],
        [InlineKeyboardButton("Назад", callback_data='back_to_main')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text("Выберите страну для новостей:", reply_markup=reply_markup)
    await update.callback_query.delete_message()

async def get_news(country_code):
    url = (f'https://newsapi.org/v2/top-headlines?'
           f'country={country_code}&'
           f'apiKey={NEWS_API_KEY}')
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        articles = data.get('articles', [])
        return articles
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching news: {e}")
        return None

async def display_news(update: Update, context: ContextTypes.DEFAULT_TYPE, country_code):
    articles = await get_news(country_code)

    if articles:
        for article in articles[:5]:  # Display the first 5 articles
            title = article.get('title', 'No Title')
            description = article.get('description', 'No Description')
            url = article.get('url', '#')
            message_text = f"<b>{title}</b>\n{description}\n<a href='{url}'>Читать далее</a>\n\n"
            try:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, parse_mode=constants.ParseMode.HTML)
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                await update.callback_query.message.reply_text("Произошла ошибка при отправке новостей.")
                return

    else:
        await update.callback_query.message.reply_text("Не удалось получить новости.")

async def news_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    country_code = query.data.split('_')[1]  # Extract country code (e.g., 'us' from 'news_us')
    await query.answer()
    await display_news(update, context, country_code)

async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Новости", callback_data='news')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text('Чем могу помочь?', reply_markup=reply_markup)
    await update.callback_query.delete_message() #Delete the previous message

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
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(CallbackQueryHandler(news_country, pattern='^news_'))
    application.add_handler(CallbackQueryHandler(back_to_main_menu, pattern='^back_to_main$'))
    application.add_handler(CallbackQueryHandler(show_news_menu, pattern='^news$'))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo))

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
