import os
import threading
import time
from flask import Flask
import telebot
import google.generativeai as genai

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
# Render требует, чтобы сервис "слушал" определенный порт.
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Мастер Подземелий на связи и охраняет королевство!", 200

def run_flask():
    # Render автоматически назначает PORT, по умолчанию используем 8080
    port = int(os.environ.get("PORT", 8080))
    print(f"Запуск веб-сервера на порту {port}...")
    try:
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Ошибка веб-сервера: {e}")

# --- НАСТРОЙКИ ТЕЛЕГРАМ И GEMINI ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

# Проверка ключей перед запуском
if not TELEGRAM_TOKEN or not GEMINI_KEY:
    print("КРИТИЧЕСКАЯ ОШИБКА: Переменные окружения TELEGRAM_TOKEN или GEMINI_KEY не найдены!")
    print("Пожалуйста, проверьте настройки (Environment Variables) в панели Render.")

# Инициализация Gemini
genai.configure(api_key=GEMINI_KEY)

# Системная инструкция для Мастера Подземелий (DM)
SYSTEM_PROMPT = """
Ты — мудрый, добрый и вдохновляющий Мастер Подземелий (DM). 
Твоя цель — вести увлекательное фэнтезийное приключение в мире D&D 5e для молодежной аудитории.
Правила игры:
1. Создавай яркие и безопасные описания: шелест листвы, сияние магических кристаллов, добрые улыбки NPC.
2. Фокусируйся на решении загадок, помощи жителям мира, исследовании древних руин и командной работе.
3. Избегай жестокости и пугающих тем. Если назревает конфликт, старайся разрешить его через смекалку, дипломатию или защитную магию.
4. Проси игроков кидать d20 для проверок (на внимательность, убеждение, ловкость) и описывай успех или забавную неудачу.
5. Пиши на русском языке в эпическом, но понятном и дружелюбном стиле.
"""

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=SYSTEM_PROMPT
)

bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
game_sessions = {}

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_msg = (
        "Приветствую, герои! 🏰✨\n\n"
        "Я — ваш Мастер Подземелий. Мы отправимся в путешествие, "
        "полное тайн и верных друзей. Опишите своего персонажа: "
        "кто вы и какая у вас мечта? Или просто скажите 'Начнем!', и я подберу вам роль."
    )
    bot.reply_to(message, welcome_msg)

@bot.message_handler(func=lambda message: True)
def handle_game_play(message):
    chat_id = message.chat.id
    
    if chat_id not in game_sessions:
        game_sessions[chat_id] = model.start_chat(history=[])
    
    chat = game_sessions[chat_id]
    
    try:
        bot.send_chat_action(chat_id, 'typing')
        response = chat.send_message(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        print(f"Ошибка API: {e}")
        bot.reply_to(message, "Кажется, магические потоки временно перепутались. Попробуйте еще раз через секунду!")

if __name__ == "__main__":
    if bot:
        # Сначала запускаем веб-сервер в отдельном потоке
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # Даем серверу секунду, чтобы "забить" порт
        time.sleep(1)
        
        print("D&D Master Bot запущен...")
        # Запускаем бота
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"Ошибка поллинга: {e}")
    else:
        print("Бот не запущен из-за отсутствия токена.")
