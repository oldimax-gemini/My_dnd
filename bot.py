import os
import threading
import time
from flask import Flask
import telebot
import google.generativeai as genai

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (СТАТУС LIVE) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Мастер Подземелий на связи и охраняет королевство!", 200

# --- КОНФИГУРАЦИЯ ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

# "gemini-1.5-flash" — отличный баланс скорости и ума
SELECTED_MODEL_TYPE = "gemini-1.5-flash" 

# Инициализация Gemini
model = None

def setup_ai():
    """Настройка нейросети и правил поведения Мастера"""
    global model
    if not GEMINI_KEY:
        print("--- [ERROR] Ключ GEMINI_KEY не найден в настройках!")
        return

    try:
        genai.configure(api_key=GEMINI_KEY)
        
        SYSTEM_PROMPT = """
        Ты — мудрый, добрый и невероятно творческий Мастер Подземелий (DM). 
        Твоя миссия — вести захватывающее фэнтезийное приключение для группы друзей.
        
        Твои правила игры:
        1. ИНДИВИДУАЛЬНОСТЬ: Игроки пишут в формате "[Имя]: сообщение". 
           Запоминай каждого! Если Алексей — гном-кузнец, а Даша — эльфийка-лучница, 
           всегда учитывай их особенности в описаниях.
        2. ОБРАЗНОСТЬ: Твои описания должны быть живыми. Описывай шепот листвы, 
           сияние древних камней и тепло костра. Сделай мир осязаемым.
        3. ДОБРОТА И ГЕРОИЗМ: Это приключение про дружбу и отвагу. Никакой жестокости, 
           вредных привычек или мрачных тем. Зло в твоем мире — это озорные духи, 
           заблудшие тени или древние загадки, которые нужно решить.
        4. НАСТАВНИЧЕСТВО: Если герои запутались, предложи им варианты (например, 
           поговорить с лесными жителями или поискать скрытую тропу).
        5. ИГРОВЫЕ КОСТИ: Для важных действий (прыжок, поиск, магия) всегда проси 
           игрока бросить d20 и описывай результат в зависимости от числа.
        6. ЯЗЫК: Говори на русском, будь вежливым, эпическим и вдохновляющим.
        """
        
        model = genai.GenerativeModel(
            model_name=SELECTED_MODEL_TYPE,
            system_instruction=SYSTEM_PROMPT
        )
        print(f"--- [LOG] Мастер готов к работе (модель: {SELECTED_MODEL_TYPE})")
    except Exception as e:
        print(f"--- [ERROR] Ошибка настройки ИИ: {e}")

# Инициализация Телеграм Бота
bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
game_sessions = {}

# --- ОБРАБОТЧИКИ КОМАНД ---

if bot:
    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        welcome_text = (
            "Приветствую, искатели приключений! 🏰✨\n\n"
            "Я — ваш Мастер Подземелий. Я слышу каждого из вас и готов сплести вашу историю в единую легенду.\n\n"
            "Представьтесь по очереди: расскажите, как зовут вашего героя, кто он по профессии и какая добрая цель ведет его вперед?"
        )
        bot.reply_to(message, welcome_text)

    @bot.message_handler(func=lambda message: True)
    def handle_game_step(message):
        chat_id = message.chat.id
        user_name = message.from_user.first_name or "Путешественник"
        
        # Логируем сообщение в консоль Render
        print(f"--- [MSG] {user_name} пишет: {message.text}")
        
        if not model:
            bot.reply_to(message, "Магия восстанавливается. Попробуйте через минуту!")
            return

        if chat_id not in game_sessions:
            game_sessions[chat_id] = model.start_chat(history=[])
        
        chat = game_sessions[chat_id]
        full_message = f"[{user_name}]: {message.text}"
        
        max_attempts = 3
        for i in range(max_attempts):
            try:
                bot.send_chat_action(chat_id, 'typing')
                response = chat.send_message(full_message)
                
                if response and response.text:
                    bot.reply_to(message, response.text)
                    return 
                break
            except Exception as e:
                if "429" in str(e):
                    if i < max_attempts - 1:
                        time.sleep(3)
                        continue
                    else:
                        bot.reply_to(message, "Мастеру нужно перевести дух (лимит запросов). Сделайте паузу на 30 секунд! 🕯️")
                else:
                    print(f"--- [ERROR] Ошибка Gemini: {e}")
                    bot.reply_to(message, "Магические потоки перепутались. Попробуйте еще раз!")
                break

def run_bot():
    """Основной цикл запуска прослушивания"""
    if not bot: return
    
    while True:
        try:
            print("--- [LOG] Запуск прослушивания Telegram...")
            bot.delete_webhook(drop_pending_updates=True)
            bot.polling(non_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"--- [ERROR] Потеряна связь: {e}. Перезапуск...")
            time.sleep(5)

# Запуск
if TELEGRAM_TOKEN:
    setup_ai()
    threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
