import os
import threading
import time
from flask import Flask
import telebot
import google.generativeai as genai

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (Health Check) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Мастер Подземелий на связи и охраняет королевство!", 200

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

# Глобальная переменная для модели ИИ
model = None

def setup_ai():
    """Динамический поиск и настройка лучшей доступной модели ИИ"""
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
                    print(f"--- [LOG] Найдена модель: {m.name}")
        except Exception as list_err:
            print(f"--- [ERROR] Не удалось получить список моделей: {list_err}")

        # Список приоритетов имен моделей (пробуем разные варианты написания)
        priority_list = [
            "models/gemini-1.5-flash-latest",
            "models/gemini-1.5-flash", 
            "models/gemini-2.0-flash",
            "models/gemini-pro"
        ]
        
        selected_model_name = None
        # Сначала ищем по нашему списку приоритетов среди доступных
        for p_model in priority_list:
            if p_model in available_models:
                selected_model_name = p_model
                break
        
        # Если ничего из списка не подошло, берем первую попавшуюся рабочую из тех, что вернул API
        if not selected_model_name and available_models:
            selected_model_name = available_models[0]
        
        # Если API ничего не вернул, пробуем стандартное имя как последний шанс
        if not selected_model_name:
            selected_model_name = "models/gemini-1.5-flash-latest"

        print(f"--- [LOG] Итоговый выбор модели для игры: {selected_model_name}")

        SYSTEM_PROMPT = """
        Ты — мудрый, добрый и вдохновляющий Мастер Подземелий (DM). 
        Твоя цель — вести увлекательное и безопасное фэнтезийное приключение в мире D&D 5e.
        
        Твои правила игры в группе:
        1. ИНДИВИДУАЛЬНОСТЬ: Игроки пишут в формате "[Имя]: сообщение". Запоминай героев! 
           Обращайся к игрокам по их именам и учитывай их выбранные классы/расы.
        2. АТМОСФЕРА: Описывай мир красиво и атмосферно: шепот ветра, сияние магии, запахи леса.
        3. ДОБРОТА: Это героическая сказка про дружбу и отвагу. Никакой жестокости или пугающих тем.
        4. ПОМОЩЬ: Подсказывай игрокам варианты действий, если они зашли в тупик.
        5. КОСТИ: Проси кидать d20 для важных действий и описывай результат эпично.
        6. ЯЗЫК: Говори на русском, будь вежливым и вдохновляющим рассказчиком.
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

# Обработчики команд
if bot:
    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        welcome_text = (
            "Приветствую, герои! 🏰✨\n\n"
            "Я — ваш Мастер Подземелий. Я вижу каждого из вас по именам и готов начать нашу легенду!\n\n"
            "Представьтесь по очереди: расскажите, как зовут вашего героя, кто он (раса/класс) и какая добрая цель ведет его вперед?"
        )
        bot.reply_to(message, welcome_text)

    @bot.message_handler(func=lambda message: True)
    def handle_game_step(message):
        chat_id = message.chat.id
        user_name = message.from_user.first_name or "Путешественник"
        
        print(f"--- [MSG] Сообщение от {user_name} в чате {chat_id}: {message.text[:50]}")
        
        if not model:
            bot.reply_to(message, "Магия всё еще настраивается. Подождите минуту.")
            return

        if chat_id not in game_sessions:
            print(f"--- [LOG] Новое приключение для чата: {chat_id}")
            game_sessions[chat_id] = model.start_chat(history=[])
        
        chat = game_sessions[chat_id]
        # Добавляем имя пользователя к тексту, чтобы ИИ различал игроков
        full_message = f"[{user_name}]: {message.text}"
        
        # Попытки отправить сообщение с обработкой лимитов (429)
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                bot.send_chat_action(chat_id, 'typing')
                response = chat.send_message(full_message)
                
                if response and response.text:
                    bot.reply_to(message, response.text)
                    return 
                break 
            except Exception as e:
                error_str = str(e)
                if "429" in error_str:
                    if attempt < max_attempts - 1:
                        print(f"--- [WARN] Лимит превышен. Попытка {attempt+1} через 3 сек...")
                        time.sleep(3)
                        continue
                    else:
                        bot.reply_to(message, "Мастер немного устал. Сделайте паузу на 20-30 секунд! ✨")
                elif "404" in error_str:
                    print("--- [ERROR] Модель не найдена (404). Пробую перенастройку...")
                    setup_ai()
                    bot.reply_to(message, "Мастер ищет новый путь в это измерение... Попробуйте отправить сообщение еще раз!")
                else:
                    print(f"--- [ERROR] Ошибка Gemini: {error_str}")
                    bot.reply_to(message, "Магический туман скрыл путь. Попробуйте еще раз через мгновение!")
                break

def run_bot():
    """Цикл работы бота с защитой от конфликтов 409"""
    if not bot: return
    
    while True:
        try:
            print("--- [LOG] Подготовка к запуску Telegram...")
            bot.delete_webhook(drop_pending_updates=True)
            time.sleep(2) # Пауза для стабильности Render при деплое
            print("--- [LOG] Запуск прослушивания Telegram...")
            bot.polling(non_stop=True, interval=0, timeout=20)
        except Exception as e:
            if "Conflict" in str(e):
                print("--- [LOG] Обнаружен конфликт (409). Ожидание 10 секунд...")
                time.sleep(10)
            else:
                print(f"--- [ERROR] Сбой связи: {e}. Рестарт через 5 секунд...")
                time.sleep(5)

# Запуск ИИ и фонового потока бота
if TELEGRAM_TOKEN:
    setup_ai()
    threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    # Запуск Flask-сервера
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
