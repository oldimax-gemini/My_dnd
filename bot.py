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
        
        # Мы используем 'gemini-1.5-flash', это самая стабильная версия.
        # Если она выдает 404, библиотека сама попробует найти нужный путь.
        SYSTEM_PROMPT = """
        Ты — мудрый, добрый и вдохновляющий Мастер Подземелий (DM). 
        Твоя цель — вести увлекательное и безопасное фэнтезийное приключение в мире D&D 5e.
        
        Твои правила:
        1. Безопасность и чистота: Веди игру в стиле добрых сказок и героических легенд. 
           Никакой жестокости, вредных привычек или пугающих тем.
        2. Атмосфера: Описывай красоту природы, магическое сияние и верную дружбу.
        3. Помощь: Если игроки (твои сверстники) не знают, что делать, подсказывай им добрые и смелые варианты.
        4. Игровой процесс: Проси кидать кубик d20 для проверок (на внимательность, доброту или ловкость).
        5. Язык: Общайся на русском языке, будь вежливым и эпическим Мастером.
        """
        
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=SYSTEM_PROMPT
        )
        print("Нейросеть успешно настроена.")
    except Exception as e:
        print(f"Ошибка настройки нейросети: {e}")

# Инициализация Бота
bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
game_sessions = {}

def run_bot():
    if not bot:
        print("Ошибка: TOKEN не найден.")
        return

    # Очистка конфликтов 409
    try:
        bot.delete_webhook(drop_pending_updates=True)
        time.sleep(2) # Даем Telegram время закрыть старые сессии
    except:
        pass

    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        welcome_text = (
            "Приветствую, юные герои! 🏰✨\n\n"
            "Я — ваш Мастер Подземелий. Вместе мы отправимся в мир, где правит дружба и магия. "
            "Кем вы хотите быть? Смелым рыцарем, добрым волшебником или лесной следопыткой?\n\n"
            "Опишите своего героя, и мы начнем!"
        )
        bot.reply_to(message, welcome_text)

    @bot.message_handler(func=lambda message: True)
    def handle_game_step(message):
        chat_id = message.chat.id
        
        if model is None:
            bot.reply_to(message, "Магия временно недоступна. Проверьте настройки ключа Gemini.")
            return

        if chat_id not in game_sessions:
            game_sessions[chat_id] = model.start_chat(history=[])
        
        try:
            bot.send_chat_action(chat_id, 'typing')
            response = game_sessions[chat_id].send_message(message.text)
            
            if response and response.text:
                bot.reply_to(message, response.text)
            else:
                bot.reply_to(message, "Мастер задумался... Попробуй описать свое действие иначе!")
                
        except Exception as e:
            print(f"Ошибка API Gemini: {e}")
            # Если модель 1.5-flash не найдена, это может быть временный сбой API Studio.
            bot.reply_to(message, "Похоже, магический туман скрыл путь. Попробуйте отправить сообщение еще раз через минуту.")

    print("Бот готов к приключениям!")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)

# Запускаем бота фоном
if TELEGRAM_TOKEN:
    threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    # Основной поток для Flask (Render)
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
