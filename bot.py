import os
import telebot
import google.generativeai as genai
from telebot import types

# --- НАСТРОЙКИ ---
# Если вы запускаете локально, замените на свои строки. 
# Если на сервере (Render/Railway), добавьте их в Environment Variables.
TOKEN = os.environ.get('TELEGRAM_TOKEN', 'ВАШ_ТЕЛЕГРАМ_ТОКЕН')
GEMINI_KEY = os.environ.get('GEMINI_KEY', 'ВАШ_GEMINI_API_KEY')

# Инициализация Gemini
genai.configure(api_key=GEMINI_KEY)

# Настройка модели (Системная инструкция для DM)
SYSTEM_PROMPT = """
Ты — профессиональный Мастер Подземелий (DM) в мире D&D 5e. 
Твоя задача: вести захватывающую, атмосферную и честную игру.
Правила:
1. Описывай окружение сочно: запахи, звуки, тени.
2. Когда игрок совершает действие, требующее проверки, проси его кинуть кубик (или имитируй бросок сам, если игрок просит).
3. Веди учет здоровья (HP) и инвентаря персонажей.
4. Будь непредсказуемым: враги могут быть хитрыми, а NPC — иметь свои тайные цели.
5. Пиши на русском языке, используя фэнтезийный стиль.
"""

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=SYSTEM_PROMPT
)

# Инициализация Бота
bot = telebot.TeleBot(TOKEN)

# Хранилище истории чатов (в памяти)
# Для серьезных игр лучше использовать базу данных, но для начала хватит и этого.
chat_sessions = {}

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "Greetings, travelers! 🎭\n\n"
        "Я — ваш верный Мастер Подземелий, воплощенный в кремнии и коде. "
        "Готовы ли вы отправиться в приключение, которое воспевают барды?\n\n"
        "Просто напишите, кто вы (раса, класс) и где начинается ваш путь, "
        "или попросите меня придумать завязку!"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: True)
def handle_game_step(message):
    chat_id = message.chat.id
    
    # Создаем или получаем сессию для этого чата
    if chat_id not in chat_sessions:
        chat_sessions[chat_id] = model.start_chat(history=[])
    
    chat = chat_sessions[chat_id]
    
    try:
        # Показываем статус "печатает", чтобы игроки не скучали
        bot.send_chat_action(chat_id, 'typing')
        
        # Отправляем сообщение в Gemini
        response = chat.send_message(message.text)
        
        # Отправляем ответ игрокам
        bot.reply_to(message, response.text)
        
    except Exception as e:
        error_msg = "Магия дала сбой (ошибка API). Попробуйте еще раз или проверьте ключи доступа."
        bot.send_message(chat_id, error_msg)
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Мастер Подземелий проснулся и ждет игроков...")
    bot.infinity_polling()
