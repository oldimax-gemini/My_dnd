import os
import threading
from flask import Flask
import telebot
import google.generativeai as genai

# --- WEB SERVER FOR RENDER ---
# Render expects a web service to listen on a port. 
# We'll use Flask to provide a simple health check.
app = Flask(__name__)

@app.route('/')
def health_check():
    return "The D&D Master is awake and watching the realm!", 200

def run_flask():
    # Render provides the PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- TELEGRAM AND GEMINI CONFIGURATION ---
# Get keys from environment variables (set these in Render Settings)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

# Initialize Gemini
genai.configure(api_key=GEMINI_KEY)

# Systematic instruction for the AI to act as a D&D Master
SYSTEM_PROMPT = """
Ты — мудрый и вдохновляющий Мастер Подземелий (DM). 
Твоя цель — вести увлекательное фэнтезийное приключение в мире D&D 5e.
Правила поведения:
1. Создавай атмосферные описания: звуки леса, блеск сокровищ, таинственный шепот.
2. Будь добрым наставником. Если игроки новички, подсказывай, какие навыки они могут использовать.
3. Стимулируй воображение и творчество. Избегай жестокости, фокусируйся на героизме, дружбе и разгадывании тайн.
4. Проси игроков бросать кубики (d20) для важных действий и описывай результат в зависимости от выпавшего числа.
5. Веди игру на русском языке в вежливом и эпическом стиле.
"""

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=SYSTEM_PROMPT
)

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Simple in-memory session storage
# In a production app, you might want to use a database
game_sessions = {}

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_msg = (
        "Приветствую, искатели приключений! 🏰✨\n\n"
        "Я — ваш автоматизированный Мастер Подземелий. "
        "Вместе мы создадим легенду! Опишите своего героя (расу и класс) "
        "или просто скажите 'Начнем приключение!', и я перенесу вас в мир магии."
    )
    bot.reply_to(message, welcome_msg)

@bot.message_handler(func=lambda message: True)
def handle_game_play(message):
    chat_id = message.chat.id
    
    # Start a new chat session with history if it doesn't exist
    if chat_id not in game_sessions:
        game_sessions[chat_id] = model.start_chat(history=[])
    
    chat = game_sessions[chat_id]
    
    try:
        # Visual feedback: "typing..."
        bot.send_chat_action(chat_id, 'typing')
        
        # Send message to Gemini
        response = chat.send_message(message.text)
        
        # Send AI response back to Telegram
        bot.reply_to(message, response.text)
        
    except Exception as e:
        print(f"Error occurred: {e}")
        bot.reply_to(message, "Ой! Похоже, в ткани мироздания возникла трещина (ошибка связи). Попробуйте еще раз через мгновение.")

if __name__ == "__main__":
    # Start the Flask web server in a separate thread
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("D&D Master Bot is starting...")
    # Start the Telegram bot polling
    bot.infinity_polling()
