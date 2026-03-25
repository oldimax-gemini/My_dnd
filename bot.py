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
        Ты — мудрый, добрый и вдохновляющий Мастер Подземелий (DM). 
        Твоя цель — вести увлекательное и безопасное фэнтезийное приключение в мире D&D 5e.
        
        Твои правила:
        1. Безопасность и чистота: Веди игру в стиле добрых сказок и героических легенд. 
           Никакой жестокости, вредных привычек или пугающих тем.
        2. Атмосфера: Описывай красоту природы, магическое сияние и верную дружбу.
        3. Помощь: Если игроки не знают, что делать, подсказывай им добрые и смелые варианты.
        4. Игровой процесс: Проси кидать кубик d20 для проверок.
        5. Язык: Общайся на русском языке, будь вежливым и эпическим Мастером.
        """
        
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=SYSTEM_PROMPT
        )
        print("--- [LOG] Нейросеть Gemini успешно настроена.")
    except Exception as e:
        print(f"--- [ERROR] Ошибка настройки Gemini: {e}")

# Инициализация Бота
bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
game_sessions = {}

def run_bot():
    if not bot:
        print("--- [ERROR] TOKEN не найден. Проверьте Environment Variables в Render.")
        return

    # Проверка валидности токена
    try:
        me = bot.get_me()
        print(f"--- [LOG] Бот @{me.username} успешно авторизован в Telegram.")
    except Exception as e:
        print(f"--- [ERROR] Ошибка авторизации токена Telegram: {e}")
        return

    # Сброс вебхуков и старых обновлений
    for i in range(3):
        try:
            print(f"--- [LOG] Попытка {i+1}: Очистка очереди сообщений...")
            bot.delete_webhook(drop_pending_updates=True)
            break
        except Exception as e:
            print(f"--- [WARNING] Не удалось сбросить очередь: {e}. Повтор...")
            time.sleep(5)

    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        welcome_text = (
            "Приветствую, юные герои! 🏰✨\n\n"
            "Я проснулся и готов к приключениям! Если я в группе, убедитесь, что я администратор.\n\n"
            "Кем вы хотите быть? Опишите героя, и начнем путь!"
        )
        bot.reply_to(message, welcome_text)

    @bot.message_handler(commands=['ping'])
    def send_ping(message):
        bot.reply_to(message, "Понг! Мастер на связи. Если вы видите это, связь с Telegram в порядке!")

    @bot.message_handler(func=lambda message: True)
    def handle_game_step(message):
        chat_id = message.chat.id
        
        if model is None:
            bot.reply_to(message, "Магия временно недоступна (ошибка нейросети).")
            return

        if chat_id not in game_sessions:
            print(f"--- [LOG] Новая сессия для чата: {chat_id}")
            game_sessions[chat_id] = model.start_chat(history=[])
        
        try:
            bot.send_chat_action(chat_id, 'typing')
            response = game_sessions[chat_id].send_message(message.text)
            
            if response and response.text:
                bot.reply_to(message, response.text)
            else:
                bot.reply_to(message, "Мастер задумался... Попробуйте другое действие!")
                
        except Exception as e:
            print(f"--- [ERROR] Ошибка Gemini API: {e}")
            bot.reply_to(message, "Магический туман скрыл путь. Повторите ваше действие чуть позже.")

    print("--- [LOG] Бот запускает бесконечный цикл прослушивания (Polling)...")
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=10)
    except Exception as e:
        print(f"--- [ERROR] Критическая ошибка поллинга: {e}")

# Запускаем бота фоном
if TELEGRAM_TOKEN:
    print("--- [LOG] Запуск фонового потока для бота...")
    threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    # Локальный запуск
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
