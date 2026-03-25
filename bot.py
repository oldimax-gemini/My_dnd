import os
import threading
import time
from flask import Flask
import telebot
import google.generativeai as genai

# --- ВЕБ-СЕРВЕР ДЛЯ СТАТУСА LIVE ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Мастер Подземелий на связи и охраняет королевство!", 200

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

# Инициализация Gemini
model = None
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        
        # Логируем доступные модели, чтобы понять причину 404, если она будет
        print("--- [LOG] Проверка доступных моделей...")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"--- [LOG] Доступна модель: {m.name}")

        SYSTEM_PROMPT = """
        Ты — мудрый и добрый Мастер Подземелий (DM). 
        Веди приключение в мире D&D 5e для детей и подростков.
        1. Описывай мир красиво и безопасно (без жестокости).
        2. Фокусируйся на дружбе, магии и загадках.
        3. Проси игроков кидать d20 для проверок.
        4. Общайся на русском языке, будь вежливым и эпическим.
        """
        
        # Используем базовое имя модели. SDK сам добавит префиксы если нужно.
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=SYSTEM_PROMPT
        )
        print("--- [LOG] Нейросеть Gemini успешно настроена.")
    except Exception as e:
        print(f"--- [ERROR] Ошибка настройки Gemini: {e}")

# Инициализация Телеграм Бота
bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
game_sessions = {}

def run_bot():
    if not bot:
        print("--- [ERROR] TELEGRAM_TOKEN не найден.")
        return

    # Сброс старых соединений (ошибка 409)
    try:
        bot.delete_webhook(drop_pending_updates=True)
        print("--- [LOG] Очередь сообщений очищена.")
    except:
        pass

    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        welcome_text = (
            "Приветствую, герои! 🏰✨\n\n"
            "Я проснулся и готов вести вас в бой (или к сокровищам)! "
            "Если я в группе, убедитесь, что я администратор.\n\n"
            "Кем вы хотите быть? Опишите своего героя!"
        )
        bot.reply_to(message, welcome_text)

    @bot.message_handler(func=lambda message: True)
    def handle_game_step(message):
        chat_id = message.chat.id
        
        if not model:
            bot.reply_to(message, "Ошибка: Нейросеть не настроена. Проверьте GEMINI_KEY.")
            return

        if chat_id not in game_sessions:
            print(f"--- [LOG] Новая игра в чате: {chat_id}")
            game_sessions[chat_id] = model.start_chat(history=[])
        
        try:
            bot.send_chat_action(chat_id, 'typing')
            response = game_sessions[chat_id].send_message(message.text)
            
            if response and response.text:
                bot.reply_to(message, response.text)
            else:
                bot.reply_to(message, "Мастер задумался... Попробуй описать действие по-другому!")
                
        except Exception as e:
            error_str = str(e)
            print(f"--- [ERROR] Ошибка Gemini: {error_str}")
            
            if "404" in error_str:
                bot.reply_to(message, "Ошибка 404: Мастер не может найти путь к этой модели. Проверьте логи сервера.")
            elif "429" in error_str:
                bot.reply_to(message, "Слишком много запросов! Мастеру нужно передохнуть 10 секунд.")
            else:
                bot.reply_to(message, "Магический туман скрыл путь. Попробуй еще раз через мгновение!")

    print("--- [LOG] Бот начал слушать сообщения...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)

# Запуск бота в фоне
if TELEGRAM_TOKEN:
    threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    # Локальный запуск (Render использует gunicorn bot:app)
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
