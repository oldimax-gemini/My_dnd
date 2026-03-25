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
        
        # Поиск доступных моделей
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
        except Exception as list_err:
            print(f"--- [ERROR] Не удалось получить список моделей: {list_err}")

        # Выбор лучшей модели (приоритет 2.5 или 2.0)
        priority_list = [
            "models/gemini-2.5-flash", 
            "models/gemini-2.0-flash", 
            "models/gemini-1.5-flash"
        ]
        
        selected_model_name = next((m for m in priority_list if m in available_models), 
                                  available_models[0] if available_models else "models/gemini-1.5-flash")

        print(f"--- [LOG] Выбрана модель для игры: {selected_model_name}")

        SYSTEM_PROMPT = """
        Ты — мудрый и вдохновляющий Мастер Подземелий (DM). 
        Твоя цель — вести одно общее приключение для группы игроков в мире D&D 5e.
        
        Важные правила для работы в группе:
        1. Различай игроков: Тебе будут присылать сообщения в формате "[Имя игрока]: сообщение". 
           Запоминай, какой персонаж (раса, класс) принадлежит каждому игроку.
        2. Обращайся по именам: Когда отвечаешь, обращайся к конкретным героям, чтобы все понимали, к кому ты обращаешься.
        3. Командная работа: Поощряй игроков действовать сообща.
        4. Безопасность и атмосфера: Веди игру в стиле добрых сказок и героических легенд. Никакой жестокости или мрачных тем.
        5. Игровой процесс: Проси игроков кидать d20 для их действий.
        6. Язык: Общайся на русском языке, будь вежливым и эпическим Мастером.
        """
        
        model = genai.GenerativeModel(
            model_name=selected_model_name,
            system_instruction=SYSTEM_PROMPT
        )
        print(f"--- [LOG] Нейросеть успешно настроена!")
    except Exception as e:
        print(f"--- [ERROR] Ошибка настройки нейросети: {e}")

# Инициализация Телеграм Бота
bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
game_sessions = {}

def run_bot():
    if not bot:
        print("--- [ERROR] TELEGRAM_TOKEN не найден.")
        return

    # Очистка очереди (повторяем при каждом рестарте цикла)
    while True:
        try:
            print("--- [LOG] Попытка запуска прослушивания Telegram...")
            bot.delete_webhook(drop_pending_updates=True)
            
            @bot.message_handler(commands=['start', 'help'])
            def send_welcome(message):
                welcome_text = (
                    "Приветствую, герои! 🏰✨\n\n"
                    "Я — ваш Мастер Подземелий. Теперь я умею различать каждого из вас по именам!\n\n"
                    "Пожалуйста, представьтесь по очереди: напишите свою расу и класс. "
                    "Например: 'Я эльф-маг по имени Лириэль'."
                )
                bot.reply_to(message, welcome_text)

            @bot.message_handler(func=lambda message: True)
            def handle_game_step(message):
                chat_id = message.chat.id
                user_name = message.from_user.first_name or "Путешественник"
                print(f"--- [MSG] Сообщение от {user_name} в чате {chat_id}: {message.text[:50]}...")
                
                if not model:
                    bot.reply_to(message, "Магия всё еще настраивается. Попробуйте через минуту.")
                    return

                if chat_id not in game_sessions:
                    print(f"--- [LOG] Начало приключения в группе: {chat_id}")
                    game_sessions[chat_id] = model.start_chat(history=[])
                
                chat = game_sessions[chat_id]
                
                try:
                    bot.send_chat_action(chat_id, 'typing')
                    full_message = f"[{user_name}]: {message.text}"
                    response = chat.send_message(full_message)
                    
                    if response and response.text:
                        bot.reply_to(message, response.text)
                    else:
                        bot.reply_to(message, "Мастер задумался... Попробуйте еще раз.")
                except Exception as e:
                    print(f"--- [ERROR] Ошибка при обработке сообщения: {e}")
                    bot.reply_to(message, "Магический туман скрыл путь. Попробуйте еще раз через мгновение!")

            # Используем polling с параметрами для стабильности
            bot.polling(non_stop=True, interval=0, timeout=20)
            
        except Exception as e:
            print(f"--- [ERROR] Цикл бота прерван: {e}. Перезапуск через 5 сек...")
            time.sleep(5)

if TELEGRAM_TOKEN:
    setup_ai()
    # Запускаем поток бота
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
