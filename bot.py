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
        
        # Получаем список реально доступных моделей
        print("--- [LOG] Поиск доступных моделей...")
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
                    print(f"--- [LOG] Найдена модель: {m.name}")
        except Exception as list_err:
            print(f"--- [ERROR] Не удалось получить список моделей: {list_err}")

        # Список приоритетов имен моделей
        priority_list = [
            "models/gemini-2.5-flash", 
            "models/gemini-1.5-flash-latest",
            "models/gemini-1.5-flash", 
            "models/gemini-pro"
        ]
        
        selected_model_name = None
        for p_model in priority_list:
            if p_model in available_models:
                selected_model_name = p_model
                break
        
        if not selected_model_name and available_models:
            selected_model_name = available_models[0]
        
        if not selected_model_name:
            selected_model_name = "models/gemini-1.5-flash-latest"

        print(f"--- [LOG] Итоговый выбор модели: {selected_model_name}")

        SYSTEM_PROMPT = """
        Ты — мудрый и вдохновляющий Мастер Подземелий (DM). 
        Твоя цель — вести ОДНО ОБЩЕЕ приключение для ГРУППЫ игроков в мире D&D 5e.
        
        Твои расширенные правила для работы в группе:
        1. ИДЕНТИФИКАЦИЯ: Сообщения приходят в формате "[Имя]: текст". Ты ОБЯЗАН запомнить, кто какой герой.
        2. ЛИСТ ОТРЯДА: Мысленно веди список: кто игрок (имя в Telegram), какая у него раса и класс. 
           Например: "Алексей — гном-воин", "Маша — эльфийка-маг".
        3. ОБРАЩЕНИЕ: Всегда отвечай конкретному человеку по имени, когда он совершает действие. 
           Пример: "Алексей, твой топор со свистом рассекает воздух!"
        4. КОМАНДА: Если кто-то новый пишет в чат, поприветствуй его и попроси представить своего персонажа.
        5. АТМОСФЕРА: Описывай мир сочно и безопасно. Никакой жестокости, вредных привычек или пугающих тем.
        6. КОСТИ: Проси кидать d20 для проверок навыков.
        7. ЯЗЫК: Говори на русском, будь добрым и эпическим рассказчиком.
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
            "Я — ваш Мастер Подземелий. Теперь я стал еще выносливее и готов вести нашу летопись!\n\n"
            "Пожалуйста, представьтесь по очереди: напишите имя вашего героя, его расу и класс. "
            "Я впишу каждого в нашу общую историю!"
        )
        bot.reply_to(message, welcome_text)

    @bot.message_handler(func=lambda message: True)
    def handle_game_step(message):
        chat_id = message.chat.id
        user_name = message.from_user.first_name or "Путешественник"
        
        # Логируем входящее сообщение
        print(f"--- [MSG] {user_name}: {message.text[:50]}")
        
        if not model:
            bot.reply_to(message, "Магия всё еще настраивается. Подождите минуту.")
            return

        # Используем chat_id для общей истории группы
        if chat_id not in game_sessions:
            print(f"--- [LOG] Новое приключение для группы в чате: {chat_id}")
            game_sessions[chat_id] = model.start_chat(history=[])
        
        chat = game_sessions[chat_id]
        full_message = f"[{user_name}]: {message.text}"
        
        # Улучшенная логика повторов для обхода лимитов (429)
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                bot.send_chat_action(chat_id, 'typing')
                response = chat.send_message(full_message)
                
                if response and response.text:
                    bot.reply_to(message, response.text)
                    return 
                break 
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str:
                    # Постепенно увеличиваем паузу: 4с, 8с, 12с...
                    wait_time = (attempt + 1) * 4
                    if attempt < max_attempts - 1:
                        print(f"--- [WARN] Лимит запросов. Ожидание {wait_time}с...")
                        time.sleep(wait_time)
                        continue
                    else:
                        bot.reply_to(message, "Мастер взял небольшую паузу, чтобы пролистать древние свитки. Давайте подождем 30 секунд, прежде чем продолжить приключение! 🕯️")
                else:
                    print(f"--- [ERROR] Ошибка Gemini: {error_str}")
                    bot.reply_to(message, "Магический туман скрыл путь. Попробуйте повторить ваше действие через мгновение!")
                break

def run_bot():
    """Цикл работы бота с защитой от конфликтов 409"""
    if not bot: return
    
    while True:
        try:
            print("--- [LOG] Подготовка к запуску Telegram...")
            bot.delete_webhook(drop_pending_updates=True)
            time.sleep(2)
            print("--- [LOG] Запуск прослушивания Telegram...")
            bot.polling(non_stop=True, interval=0, timeout=20)
        except Exception as e:
            if "conflict" in str(e).lower():
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
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
