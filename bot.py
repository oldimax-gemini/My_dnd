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
    return "The Dungeon Master is online and guarding the realm!", 200

# --- КОНФИГУРАЦИЯ ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

# Инициализация Gemini
model = None

def setup_ai():
    global model
    if not GEMINI_KEY:
        print("--- [ERROR] GEMINI_KEY не найден в переменных окружения!")
        return

    try:
        genai.configure(api_key=GEMINI_KEY)
        
        # Получаем список реально доступных моделей для этого ключа
        print("--- [LOG] Поиск доступных моделей...")
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
        except Exception as list_err:
            print(f"--- [ERROR] Не удалось получить список моделей: {list_err}")

        # Список приоритетных моделей (от новейших к стабильным)
        # В твоих логах были gemini-2.5-flash и gemini-2.0-flash
        priority_list = [
            "models/gemini-2.5-flash", 
            "models/gemini-2.0-flash", 
            "models/gemini-1.5-flash",
            "models/gemini-pro"
        ]
        
        selected_model_name = None
        for p_model in priority_list:
            if p_model in available_models:
                selected_model_name = p_model
                break
        
        # Если ничего из списка не подошло, берем первую попавшуюся рабочую
        if not selected_model_name and available_models:
            selected_model_name = available_models[0]
        
        # Если совсем ничего нет (крайний случай)
        if not selected_model_name:
            selected_model_name = "models/gemini-1.5-flash"

        print(f"--- [LOG] Выбрана модель для игры: {selected_model_name}")

        SYSTEM_PROMPT = """
        Ты — мудрый, добрый и вдохновляющий Мастер Подземелий (DM). 
        Твоя цель — вести увлекательное, здоровое и безопасное фэнтезийное приключение в мире D&D 5e.
        
        Твои правила:
        1. Безопасность и доброта: Веди игру в стиле героических сказок. Никакой жестокости, вредных привычек или пугающих тем.
        2. Атмосфера: Описывай красоту природы, магическое сияние и верную дружбу.
        3. Помощь: Если игроки не знают, что делать, подсказывай им добрые и смелые варианты.
        4. Игровой процесс: Проси кидать кубик d20 для проверок (на внимательность, доброту, ловкость или силу).
        5. Язык: Общайся на русском языке, будь вежливым и эпическим Мастером.
        """
        
        model = genai.GenerativeModel(
            model_name=selected_model_name,
            system_instruction=SYSTEM_PROMPT
        )
        print(f"--- [LOG] Нейросеть успешно настроена на {selected_model_name}!")
    except Exception as e:
        print(f"--- [ERROR] Ошибка настройки нейросети: {e}")

# Инициализация Телеграм Бота
bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
game_sessions = {}

def run_bot():
    if not bot:
        print("--- [ERROR] TELEGRAM_TOKEN не найден.")
        return

    # Сброс вебхуков для решения ошибки 409
    try:
        bot.delete_webhook(drop_pending_updates=True)
        print("--- [LOG] Очередь Telegram очищена.")
    except Exception as e:
        print(f"--- [WARNING] Не удалось очистить очередь: {e}")

    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        welcome_text = (
            "Приветствую, герои! 🏰✨\n\n"
            "Я нашел верный путь через туман и готов к приключениям! "
            "Я ваш Мастер Подземелий. Вместе мы создадим историю о дружбе и отваге.\n\n"
            "Кем вы хотите быть? Опишите своего героя (расу, класс) и начнем путь!"
        )
        bot.reply_to(message, welcome_text)

    @bot.message_handler(func=lambda message: True)
    def handle_game_step(message):
        chat_id = message.chat.id
        
        if not model:
            bot.reply_to(message, "Магия всё еще настраивается. Подождите минуту и попробуйте снова.")
            return

        # Инициализируем сессию, если её нет
        if chat_id not in game_sessions:
            print(f"--- [LOG] Новое приключение для чата: {chat_id}")
            game_sessions[chat_id] = model.start_chat(history=[])
        
        try:
            bot.send_chat_action(chat_id, 'typing')
            response = game_sessions[chat_id].send_message(message.text)
            
            if response and response.text:
                bot.reply_to(message, response.text)
            else:
                bot.reply_to(message, "Мастер глубоко задумался... Попробуйте другое действие!")
                
        except Exception as e:
            error_str = str(e)
            print(f"--- [ERROR] Ошибка Gemini: {error_str}")
            if "404" in error_str:
                bot.reply_to(message, "Этот путь всё еще закрыт туманом (ошибка модели). Я пытаюсь найти обходную дорогу, попробуйте написать еще раз через минуту!")
                # Пробуем перенастроить ИИ в фоне, если произошла ошибка 404
                threading.Thread(target=setup_ai).start()
            else:
                bot.reply_to(message, "Магический туман скрыл путь. Попробуйте еще раз через мгновение!")

    print("--- [LOG] Бот начал слушать сообщения...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)

# Запуск настройки и бота
if TELEGRAM_TOKEN:
    setup_ai()
    threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
