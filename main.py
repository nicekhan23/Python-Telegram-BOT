import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from config import BOT_TOKEN, ADMIN_IDS, DB_PATH
from database import Database
from payments import payments_router
from video_handler import video_router

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database(DB_PATH)

# Подключаем роутеры
dp.include_router(payments_router)
dp.include_router(video_router)

# Состояния для FSM
class UserStates(StatesGroup):
    choosing_course = State()
    watching_lesson = State()
    taking_test = State()

# Клавиатуры
def main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚽ Мои курсы", callback_data="my_courses")],
        [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="my_progress")],
        [InlineKeyboardButton(text="🎯 Тестирование", callback_data="testing")],
        [InlineKeyboardButton(text="💰 Купить курс", callback_data="buy_course")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ])
    return keyboard

def admin_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Статистика пользователей", callback_data="admin_stats")],
        [InlineKeyboardButton(text="➕ Добавить урок", callback_data="admin_add_lesson")],
        [InlineKeyboardButton(text="📝 Управление заданиями", callback_data="admin_tasks")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
    ])
    return keyboard

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
    ]])

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Неизвестно"
    full_name = message.from_user.full_name or "Неизвестно"
    
    # Регистрируем пользователя
    db.add_user(user_id, username, full_name)
    
    welcome_text = (
        f"⚽ Привет, {full_name}!\n\n"
        "🎉 Добро пожаловать в нашу футбольную школу!\n\n"
        "Здесь ты сможешь:\n"
        "📚 Изучать технику футбола\n"
        "🎥 Смотреть обучающие видео\n"
        "🎯 Выполнять задания и тесты\n"
        "⭐ Зарабатывать очки за успехи\n"
        "📊 Отслеживать свой прогресс\n\n"
        "Выбери действие из меню ниже:"
    )
    
    # Проверяем, является ли пользователь админом
    if user_id in ADMIN_IDS:
        await message.answer(
            welcome_text + "\n\n🔧 <b>Админ-панель доступна!</b>", 
            reply_markup=admin_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(welcome_text, reply_markup=main_menu_keyboard())

# Возврат в главное меню
@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id in ADMIN_IDS:
        await callback.message.edit_text(
            "🏠 <b>Главное меню</b>\n🔧 Админ-панель доступна!",
            reply_markup=admin_keyboard(),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            "🏠 <b>Главное меню</b>\nВыбери действие:",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )

# Показать курсы
@dp.callback_query(F.data == "my_courses")
async def show_courses(callback: CallbackQuery):
    courses = db.get_courses()
    
    if not courses:
        await callback.message.edit_text(
            "📚 Курсы пока недоступны.\n\n"
            "🔔 Курсы добавляются администраторами.\n"
            "Обратитесь к поддержке для получения информации.",
            reply_markup=back_button()
        )
        return
    
    text = "⚽ <b>Доступные курсы:</b>\n\n"
    keyboard_buttons = []
    
    for course_id, title, description, price in courses:
        text += (
            f"📖 <b>{title}</b>\n"
            f"{description}\n"
            f"💰 <b>Цена:</b> {price} руб.\n\n"
        )
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"📖 {title}", 
                callback_data=f"course_{course_id}"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")
    ])
    
    await callback.message.edit_text(
        text, 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
        parse_mode="HTML"
    )

# Показать прогресс
@dp.callback_query(F.data == "my_progress")
async def show_progress(callback: CallbackQuery):
    user_id = callback.from_user.id
    progress = db.get_user_progress(user_id)
    
    # Определяем уровень на основе очков
    points = progress['total_points']
    if points < 100:
        level = "🥉 Новичок"
        level_emoji = "🌱"
    elif points < 500:
        level = "🥈 Любитель"
        level_emoji = "⚡"
    elif points < 1000:
        level = "🥇 Эксперт"
        level_emoji = "🔥"
    else:
        level = "🏆 Мастер"
        level_emoji = "⭐"
    
    progress_text = (
        f"📊 <b>Твой прогресс:</b>\n\n"
        f"{level_emoji} <b>Уровень:</b> {level}\n"
        f"⭐ <b>Всего очков:</b> {points}\n"
        f"📚 <b>Пройдено уроков:</b> {progress['completed_lessons']}\n"
        f"✅ <b>Выполнено заданий:</b> {progress['completed_tasks']}\n\n"
        f"💪 Продолжай тренироваться!\n"
        f"До следующего уровня: {max(0, (((points // 100) + 1) * 100) - points)} очков"
    )
    
    await callback.message.edit_text(
        progress_text,
        reply_markup=back_button(),
        parse_mode="HTML"
    )

# Показать тестирование
@dp.callback_query(F.data == "testing")
async def show_testing(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎯 <b>Раздел тестирования</b>\n\n"
        "Здесь ты можешь пройти различные тесты "
        "и проверить свои знания в футболе!\n\n"
        "Выбери тип теста:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Теоретический тест", callback_data="theory_test")],
            [InlineKeyboardButton(text="⚽ Практическое задание", callback_data="practical_test")],
            [InlineKeyboardButton(text="🧠 Тест на правила", callback_data="rules_test")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
        ]),
        parse_mode="HTML"
    )

# Теоретический тест (пример)
@dp.callback_query(F.data == "theory_test")
async def theory_test(callback: CallbackQuery):
    test_question = (
        "📝 <b>Теоретический тест - Вопрос 1/5</b>\n\n"
        "❓ <b>Сколько игроков находится на поле "
        "от одной команды во время матча?</b>\n\n"
        "Выбери правильный ответ:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A) 10 игроков", callback_data="answer_a")],
        [InlineKeyboardButton(text="B) 11 игроков", callback_data="answer_b")],
        [InlineKeyboardButton(text="C) 12 игроков", callback_data="answer_c")],
        [InlineKeyboardButton(text="🔙 Назад к тестам", callback_data="testing")]
    ])
    
    await callback.message.edit_text(test_question, reply_markup=keyboard, parse_mode="HTML")

# Обработка ответа теста
@dp.callback_query(F.data.in_(["answer_a", "answer_b", "answer_c"]))
async def handle_test_answer(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if callback.data == "answer_b":  # Правильный ответ
        points_earned = 20
        db.add_points(user_id, points_earned)
        
        result_text = (
            "✅ <b>Правильно!</b>\n\n"
            f"🎉 Ты заработал {points_earned} очков!\n\n"
            "В футболе на поле от одной команды "
            "находится 11 игроков (включая вратаря).\n\n"
            "Продолжай изучать футбол! 💪"
        )
    else:
        result_text = (
            "❌ <b>Неправильно</b>\n\n"
            "Правильный ответ: <b>11 игроков</b>\n\n"
            "В футболе на поле от одной команды "
            "находится 11 игроков (включая вратаря).\n\n"
            "Не расстраивайся, продолжай учиться! 📚"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Следующий вопрос", callback_data="theory_test")],
        [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="my_progress")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(result_text, reply_markup=keyboard, parse_mode="HTML")

# Покупка курса
@dp.callback_query(F.data == "buy_course")
async def buy_course(callback: CallbackQuery):
    courses = db.get_courses()
    
    if not courses:
        await callback.message.edit_text(
            "📚 Курсы пока недоступны для покупки.",
            reply_markup=back_button()
        )
        return
    
    text = "💰 <b>Покупка курсов</b>\n\n"
    keyboard_buttons = []
    
    for course_id, title, description, price in courses:
        text += f"📖 <b>{title}</b> - {price} руб.\n"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"💳 Купить {title}", 
                callback_data=f"purchase_{course_id}"
            )
        ])
    
    text += "\n💡 <i>Выберите курс для покупки:</i>"
    keyboard_buttons.append([
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
        parse_mode="HTML"
    )

# Помощь
@dp.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    help_text = (
        "ℹ️ <b>Справка по боту</b>\n\n"
        
        "🎯 <b>Как пользоваться ботом:</b>\n\n"
        
        "1️⃣ <b>Курсы</b> - просматривай доступные курсы обучения\n"
        "2️⃣ <b>Прогресс</b> - следи за своими достижениями\n"
        "3️⃣ <b>Тестирование</b> - проходи тесты и зарабатывай очки\n"
        "4️⃣ <b>Покупка</b> - приобретай курсы для обучения\n\n"
        
        "⭐ <b>Система очков:</b>\n"
        "• За просмотр урока: 10 очков\n"
        "• За правильный ответ в тесте: 20 очков\n"
        "• За выполнение задания: 30 очков\n\n"
        
        "🏆 <b>Уровни:</b>\n"
        "🌱 Новичок: 0-99 очков\n"
        "⚡ Любитель: 100-499 очков\n"
        "🔥 Эксперт: 500-999 очков\n"
        "⭐ Мастер: 1000+ очков\n\n"
        
        "❓ По вопросам обращайтесь к администрации."
    )
    
    await callback.message.edit_text(
        help_text,
        reply_markup=back_button(),
        parse_mode="HTML"
    )

# Админ статистика
@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет прав доступа!")
        return
    
    # Здесь будет статистика
    stats_text = (
        "📊 <b>Статистика бота</b>\n\n"
        "👥 Всего пользователей: 0\n"
        "📚 Активных курсов: 3\n"
        "✅ Выполненных заданий: 0\n\n"
        "📈 <i>Статистика обновляется в реальном времени</i>"
    )
    
    await callback.message.edit_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Админ-панель", callback_data="main_menu")
        ]]),
        parse_mode="HTML"
    )

# Основная функция
async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🤖 Бот запускается...")
    print(f"📋 База данных: {DB_PATH}")
    
    # Удаляем webhook и запускаем polling
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Бот остановлен")