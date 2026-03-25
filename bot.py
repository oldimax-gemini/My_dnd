import os
import threading
import telebot
import google.generativeai as genai
from flask import Flask

# --- ВЕБ-СЕРВЕР (ДЛЯ СТАТУСА LIVE НА RENDER) ---
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
        1. Описывай мир красиво и атмосферно: сияние древних рун, шепот ветра, добрые города.
        2. Будь добрым наставником. Помогай игрокам и подсказывай правила.
        3. Фокусируйся на героизме, разгадывании загадок и помощи жителям мира. 
        4. Избегай мрачных или пугающих тем. Вся магия и сражения — в духе добрых легенд.
        5. Проси игроков бросать кубик d20 для важных действий.
        6. Веди игру на русском языке в вежливом и эпическом стиле.
        """
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=SYSTEM_PROMPT
        )
        print("Нейросеть Gemini успешно настроена.")
    except Exception as e:
        print(f"Ошибка при настройке Gemini: {e}")

# Инициализация Бота
bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
game_sessions = {}

def run_bot():
    if not bot:
        print("КРИТИЧЕСКАЯ ОШИБКА: TELEGRAM_TOKEN не найден.")
        return

    # Очистка очереди сообщений
    try:
        bot.delete_webhook(drop_pending_updates=True)
    except:
        pass

    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        welcome_text = (
            "Приветствую, герои! 🏰✨\n\n"
            "Я — ваш верный Мастер Подземелий. Вместе мы напишем легенду о дружбе и отваге! "
            "Опишите своего персонажа: кто вы и какая у вас цель? Или просто скажите 'Начнем!', и я предложу вам роль."
        )
        bot.reply_to(message, welcome_text)

    @bot.message_handler(func=lambda message: True)
    def handle_game_step(message):
        chat_id = message.chat.id
        
        if model is None:
            bot.reply_to(message, "Ошибка: Ключ нейросети не найден. Проверьте настройки Render.")
            return

        if chat_id not in game_sessions:
            game_sessions[chat_id] = model.start_chat(history=[])
        
        chat = game_sessions[chat_id]
        
        try:
            bot.send_chat_action(chat_id, 'typing')
            response = chat.send_message(message.text)
            bot.reply_to(message, response.text)
        except Exception as e:
            print(f"Ошибка API Gemini: {e}")
            bot.reply_to(message, "Магические потоки немного запутались. Попробуйте еще раз через пару секунд!")

    print("Бот готов к приключениям!")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

# Запускаем бота в отдельном потоке сразу при запуске файла
if TELEGRAM_TOKEN:
    threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    # Локальный запуск (для тестов)
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
