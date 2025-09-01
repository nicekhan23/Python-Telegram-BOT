import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ID администраторов (замените на ваш ID)
ADMIN_IDS = [1029372329]  # Здесь укажите ваш Telegram ID

# Настройки базы данных
DB_PATH = "football_bot.db"

# Настройки платежей
PAYMENT_PROVIDER_TOKEN = ""  # Заполните позже

# Цены курсов (в копейках для Telegram Payments)
COURSE_PRICES = {
    "basic": 199000,  # 1990 рублей
    "advanced": 299000,  # 2990 рублей
    "premium": 499000   # 4990 рублей
}