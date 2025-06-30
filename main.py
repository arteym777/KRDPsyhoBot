
"""
Телеграм-бот "Мой психолог" с интеграцией YandexGPT 3 (YaLM 2.0)

Перед запуском добавьте в Secrets:
- TELEGRAM_TOKEN: токен от BotFather
- YANDEX_API_KEY: ключ API Yandex Cloud
- YANDEX_FOLDER_ID: ID папки в Yandex Cloud

Функции:
- Контекстный диалог с сохранением истории
- Психологическая поддержка через YandexGPT
- Команды /start, /reset, /help
- Обработка длинных сообщений
- Фильтрация контента
"""

import os
import logging
import time
import asyncio
import json
import requests
from typing import Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Импорт модулей для хостинга
from keep_alive import start_keep_alive_thread
from health_check import HealthChecker

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
YANDEX_API_KEY = os.environ.get("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.environ.get("YANDEX_FOLDER_ID")

if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN не найден в переменных окружения!")
    exit(1)

if not YANDEX_API_KEY:
    logger.error("YANDEX_API_KEY не найден в переменных окружения!")
    exit(1)

if not YANDEX_FOLDER_ID:
    logger.error("YANDEX_FOLDER_ID не найден в переменных окружения!")
    exit(1)

# URL для YandexGPT API
YANDEX_GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

# Хранение сессий пользователей (user_id: список сообщений)
user_sessions: Dict[int, List[Dict[str, str]]] = {}

# Максимальное количество сообщений в истории
MAX_HISTORY = 10

# Инициализация health checker
health_checker = HealthChecker()

# Системный промт для психолога
SYSTEM_PROMPT = """Ты добрый друг-психолог, который умеет слушать и поддерживать. 

Твой стиль общения:
- Говори просто и по-человечески, как близкий друг
- Используй разнообразные фразы и выражения, не повторяйся
- Варьируй способы выражения поддержки и понимания
- Будь искренним и эмпатичным
- Задавай вопросы по-разному каждый раз
- Используй эмодзи для создания теплой атмосферы, но не в каждом сообщении
- Избегай шаблонных психологических фраз
- Говори живым разговорным языком

Примеры разнообразных фраз:
Вместо "Я понимаю" используй: "Чувствую тебя", "Представляю", "Это непросто", "Слышу тебя"
Вместо "Расскажи больше" говори: "Что еще важно?", "А как это было?", "Интересно узнать подробнее"
Вместо "Как ты себя чувствуешь?" спрашивай: "Что сейчас внутри?", "Какие ощущения?", "Что происходит в душе?"

Стиль ответа: живой, разнообразный, искренний. Максимум 2-3 предложения.
Отвечай на русском языке."""


async def check_content_safety(text: str) -> bool:
    """Простая проверка контента на недопустимые слова"""
    try:
        # Базовая фильтрация - можно расширить
        forbidden_words = ["убийство", "самоубийство", "суицид", "наркотики"]
        text_lower = text.lower()
        
        for word in forbidden_words:
            if word in text_lower:
                return False
        return True
    except Exception as e:
        logger.warning(f"Ошибка модерации: {e}")
        return True


async def generate_yandex_gpt_response(messages: List[Dict[str, str]]) -> str:
    """Генерация ответа через YandexGPT 3"""
    try:
        # Добавляем небольшую задержку для избежания лимитов API
        await asyncio.sleep(1)
        
        # Формируем контекст для YandexGPT
        context_text = ""
        user_message = ""
        
        for msg in messages:
            if msg["role"] == "system":
                context_text = msg["content"]
            elif msg["role"] == "user":
                user_message = msg["content"]
        
        # Объединяем системный промт с последним сообщением пользователя
        full_prompt = f"{context_text}\n\nПользователь: {user_message}\n\nПсихолог:"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {YANDEX_API_KEY}"
        }
        
        data = {
            "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": 0.8,
                "maxTokens": 300
            },
            "messages": [
                {
                    "role": "system",
                    "text": context_text
                },
                {
                    "role": "user", 
                    "text": user_message
                }
            ]
        }
        
        # Выполняем синхронный запрос в отдельном потоке
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: requests.post(YANDEX_GPT_URL, headers=headers, json=data, timeout=30)
        )
        
        if response.status_code == 200:
            result = response.json()
            if "result" in result and "alternatives" in result["result"]:
                return result["result"]["alternatives"][0]["message"]["text"]
            else:
                logger.error(f"Неожиданная структура ответа YandexGPT: {result}")
                return "Извините, произошла ошибка при получении ответа. Попробуйте еще раз."
        else:
            logger.error(f"Ошибка YandexGPT API: {response.status_code} - {response.text}")
            return "Извините, у меня временные технические трудности. Попробуйте повторить через минуту."
            
    except Exception as e:
        logger.error(f"Ошибка YandexGPT API: {e}")
        return "Извините, у меня временные технические трудности. Попробуйте повторить через минуту. Я здесь, чтобы вас поддержать."


def split_long_message(text: str, max_length: int = 4000) -> List[str]:
    """Разбивка длинных сообщений на части"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_part = ""
    
    # Разбиваем по предложениям
    sentences = text.split('. ')
    
    for sentence in sentences:
        if len(current_part + sentence + '. ') <= max_length:
            current_part += sentence + '. '
        else:
            if current_part:
                parts.append(current_part.strip())
                current_part = sentence + '. '
            else:
                # Если предложение слишком длинное, разбиваем принудительно
                parts.append(sentence[:max_length])
                current_part = sentence[max_length:] + '. '
    
    if current_part:
        parts.append(current_part.strip())
    
    return parts


def get_user_session(user_id: int) -> List[Dict[str, str]]:
    """Получение сессии пользователя"""
    if user_id not in user_sessions:
        user_sessions[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return user_sessions[user_id]


def add_to_session(user_id: int, role: str, content: str):
    """Добавление сообщения в сессию с ограничением истории"""
    session = get_user_session(user_id)
    session.append({"role": role, "content": content})
    
    # Оставляем только системный промт + последние MAX_HISTORY сообщений
    if len(session) > MAX_HISTORY + 1:
        session = [session[0]] + session[-(MAX_HISTORY):]
        user_sessions[user_id] = session


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "друг"
    
    # Сброс сессии
    user_sessions[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Создаем кнопку для начала сессии
    keyboard = [[InlineKeyboardButton("🌟 Начать сессию", callback_data="start_session")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
👋 Привет, {user_name}! Я твой психолог, и я готов тебя выслушать.

😊 Я умею:
• Поддержать в трудную минуту
• Помочь разобраться в чувствах  
• Просто поговорить по душам

💬 Можешь рассказать мне всё, что на сердце. Я не сужу и не ставлю диагнозы — просто слушаю и поддерживаю.

Команды: /help /reset

О чём хочешь поговорить? 🤗
"""
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)


async def start_session_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки начала сессии"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🌟 Сессия начата! Я готов вас выслушать.\n\n"
        "Поделитесь тем, что у вас на душе. Не стесняйтесь выражать свои чувства — "
        "здесь вы в безопасности."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
🔧 **Доступные команды:**

/start — перезапустить бота и увидеть приветствие
/reset — сбросить историю диалога и начать заново
/help — показать эту справку

💡 **Как пользоваться ботом:**

1. Просто напишите мне о том, что вас беспокоит
2. Я буду задавать уточняющие вопросы
3. Вместе мы попробуем разобраться в ситуации
4. Если нужно начать заново — используйте /reset

🔒 **Конфиденциальность:**
Ваши сообщения не сохраняются после завершения сессии.

❤️ **Помните:** Я здесь, чтобы поддержать вас!

🔬 *Работает на YandexGPT 3 (YaLM 2.0)*
"""
    await update.message.reply_text(help_text)


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /reset"""
    user_id = update.effective_user.id
    user_sessions[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    await update.message.reply_text(
        "🔄 История диалога сброшена.\n\n"
        "Мы можем начать разговор с чистого листа. "
        "О чем бы вы хотели поговорить?"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    user_text = update.message.text
    
    # Проверка безопасности контента
    if not await check_content_safety(user_text):
        await update.message.reply_text(
            "Извините, но я не могу обсуждать такие темы. "
            "Давайте поговорим о чем-то другом, что вас беспокоит."
        )
        return
    
    # Показываем, что бот печатает
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        # Выполняем проверку здоровья приложения
        health_checker.perform_check()
        
        # Добавляем сообщение пользователя в сессию
        add_to_session(user_id, "user", user_text)
        
        # Получаем ответ от YandexGPT
        session = get_user_session(user_id)
        gpt_response = await generate_yandex_gpt_response(session)
        
        # Добавляем ответ бота в сессию
        add_to_session(user_id, "assistant", gpt_response)
        
        # Разбиваем длинные ответы на части
        message_parts = split_long_message(gpt_response)
        
        for i, part in enumerate(message_parts):
            await update.message.reply_text(part)
            # Небольшая пауза между частями
            if i < len(message_parts) - 1:
                await asyncio.sleep(0.5)
                
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}")
        await update.message.reply_text(
            "Произошла ошибка при обработке вашего сообщения. "
            "Попробуйте написать еще раз через минуту."
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}")
    if update and update.message:
        await update.message.reply_text(
            "Извините, произошла техническая ошибка. "
            "Попробуйте повторить запрос через минуту."
        )


def main():
    """Основная функция запуска бота"""
    logger.info("Запуск Telegram-бота 'Мой психолог' с YandexGPT...")
    
    # Запуск HTTP сервера для поддержания активности
    start_keep_alive_thread(health_checker)
    
    # Создание приложения
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Добавление обработчиков команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("reset", reset_command))
    
    # Обработчик кнопки начала сессии
    application.add_handler(CallbackQueryHandler(start_session_callback, pattern="start_session"))
    
    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запуск бота
    logger.info("Бот запущен и готов к работе!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
