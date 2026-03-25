import os
import threading
import time
from flask import Flask
import telebot
import google.generativeai as genai

# --- ВЕБ-СЕРВЕР (ДЛЯ RENDER) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Мастер Подземелий на связи и охраняет королевство!", 200

# --- НАСТРОЙКИ ТЕЛЕГРАМ И GEMINI ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

# Настройка Gemini
model = None
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        SYSTEM_PROMPT = """
        Ты — мудрый и вдохновляющий Мастер Подземелий (DM). 
        Твоя цель — вести увлекательное фэнтезийное приключение в мире D&D 5e.
        Правила поведения:
        1. Описывай мир красиво и атмосферно.
        2. Будь добрым наставником, помогай игрокам и подсказывай правила.
        3. Фокусируйся на героизме, разгадывании загадок и командной работе. 
        4. Избегай мрачных или пугающих тем.
        5. Веди игру на русском языке.
        """
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=SYSTEM_PROMPT
        )
        print("Нейросеть Gemini успешно настроена.")
    except Exception as e:
        print(f"Ошибка настройки Gemini: {e}")

# Инициализация Бота
bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
game_sessions = {}

def run_bot():
    if not bot:
        print("Ошибка: Токен Telegram не найден.")
        return

    # РЕШЕНИЕ ОШИБКИ 409: Очищаем старые соединения перед запуском
    try:
        print("Сброс старых соединений Telegram...")
        bot.delete_webhook(drop_pending_updates=True)
        time.sleep(1) # Короткая пауза для стабильности
    except Exception as e:
        print(f"Заметка по webhook: {e}")

    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        bot.reply_to(message, "Приветствую, герои! 🏰 Я ваш Мастер Подземелий. Опишите персонажа и начнем!")

    @bot.message_handler(func=lambda message: True)
    def handle_game_step(message):
        chat_id = message.chat.id
        if model is None:
            bot.reply_to(message, "Ошибка: Настройте API ключ нейросети.")
            return

        if chat_id not in game_sessions:
            game_sessions[chat_id] = model.start_chat(history=[])
        
        try:
            bot.send_chat_action(chat_id, 'typing')
            response = game_sessions[chat_id].send_message(message.text)
            bot.reply_to(message, response.text)
        except Exception as e:
            print(f"Ошибка API: {e}")
            bot.reply_to(message, "Магия немного запуталась. Попробуйте еще раз!")

    print("Бот запускает прослушивание сообщений...")
    # Используем long_polling для большей стабильности на сервере
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

# Запуск бота в отдельном потоке (работает при импорте gunicorn)
if TELEGRAM_TOKEN:
    threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    # Локальный запуск
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
