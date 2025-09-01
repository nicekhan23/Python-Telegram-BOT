import asyncio
import logging
import sqlite3
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

# Обработка выбора конкретного курса
@dp.callback_query(F.data.startswith("course_"))
async def show_specific_course(callback: CallbackQuery):
    course_id = callback.data.replace("course_", "")
    courses = db.get_courses()
    
    selected_course = None
    for course in courses:
        if str(course[0]) == course_id:
            selected_course = course
            break
    
    if not selected_course:
        await callback.answer("❌ Курс не найден!")
        return
    
    course_id_int, title, description, price = selected_course
    
    course_text = (
        f"📖 <b>{title}</b>\n\n"
        f"📝 <b>Описание:</b>\n{description}\n\n"
        f"💰 <b>Цена:</b> {price} руб.\n\n"
        f"📚 В этом курсе вы изучите основы футбола и получите практические навыки."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить курс", callback_data=f"purchase_{course_id}")],
        [InlineKeyboardButton(text="🎥 Посмотреть урок (демо)", callback_data=f"demo_lesson_{course_id}")],
        [InlineKeyboardButton(text="🔙 К курсам", callback_data="my_courses")]
    ])
    
    await callback.message.edit_text(course_text, reply_markup=keyboard, parse_mode="HTML")

# Демо урок
@dp.callback_query(F.data.startswith("demo_lesson_"))
async def show_demo_lesson(callback: CallbackQuery):
    course_id = callback.data.replace("demo_lesson_", "")
    
    demo_text = (
        f"🎥 <b>Демо урок - Основы дриблинга</b>\n\n"
        f"📝 В этом уроке вы изучите:\n"
        f"• Основные принципы дриблинга\n"
        f"• Техника ведения мяча\n"
        f"• Практические упражнения\n\n"
        f"⏱ Длительность: 15 минут\n"
        f"⭐ За прохождение: +10 очков\n\n"
        f"💡 Это демонстрационный урок. Полные уроки доступны после покупки курса."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Урок просмотрен", callback_data=f"complete_demo_{course_id}")],
        [InlineKeyboardButton(text="💳 Купить полный курс", callback_data=f"purchase_{course_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"course_{course_id}")]
    ])
    
    await callback.message.edit_text(demo_text, reply_markup=keyboard, parse_mode="HTML")

# Завершение демо урока
@dp.callback_query(F.data.startswith("complete_demo_"))
async def complete_demo_lesson(callback: CallbackQuery):
    user_id = callback.from_user.id
    course_id = callback.data.replace("complete_demo_", "")
    
    # Добавляем очки за демо урок
    db.add_points(user_id, 10)
    
    completion_text = (
        f"🎉 <b>Демо урок пройден!</b>\n\n"
        f"✅ Вы получили +10 очков\n"
        f"📊 Ваш текущий прогресс обновлен\n\n"
        f"💡 Хотите изучить больше? Приобретите полный курс!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить полный курс", callback_data=f"purchase_{course_id}")],
        [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="my_progress")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(completion_text, reply_markup=keyboard, parse_mode="HTML")

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
        next_level_points = 100
    elif points < 500:
        level = "🥈 Любитель"
        level_emoji = "⚡"
        next_level_points = 500
    elif points < 1000:
        level = "🥇 Эксперт"
        level_emoji = "🔥"
        next_level_points = 1000
    else:
        level = "🏆 Мастер"
        level_emoji = "⭐"
        next_level_points = points  # Уже максимальный уровень
    
    progress_text = (
        f"📊 <b>Твой прогресс:</b>\n\n"
        f"{level_emoji} <b>Уровень:</b> {level}\n"
        f"⭐ <b>Всего очков:</b> {points}\n"
        f"📚 <b>Пройдено уроков:</b> {progress['completed_lessons']}\n"
        f"✅ <b>Выполнено заданий:</b> {progress['completed_tasks']}\n\n"
    )
    
    if next_level_points > points:
        progress_text += f"🎯 До следующего уровня: {next_level_points - points} очков\n"
    else:
        progress_text += "🏆 Максимальный уровень достигнут!\n"
    
    progress_text += "\n💪 Продолжай тренироваться!"
    
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
        [InlineKeyboardButton(text="A) 10 игроков", callback_data="answer_a_1")],
        [InlineKeyboardButton(text="B) 11 игроков", callback_data="answer_b_1")],
        [InlineKeyboardButton(text="C) 12 игроков", callback_data="answer_c_1")],
        [InlineKeyboardButton(text="🔙 Назад к тестам", callback_data="testing")]
    ])
    
    await callback.message.edit_text(test_question, reply_markup=keyboard, parse_mode="HTML")

# Практическое задание
@dp.callback_query(F.data == "practical_test")
async def practical_test(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚽ <b>Практическое задание</b>\n\n"
        "📋 <b>Задание:</b> Выполните 20 жонглирований мячом\n\n"
        "📝 <b>Инструкции:</b>\n"
        "1. Возьмите футбольный мяч\n"
        "2. Жонглируйте любой частью тела кроме рук\n"
        "3. Сосчитайте количество касаний\n"
        "4. Отметьте выполнение ниже\n\n"
        "⭐ <b>За выполнение:</b> +30 очков",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Задание выполнено", callback_data="complete_practical")],
            [InlineKeyboardButton(text="📹 Посмотреть видео-пример", callback_data="show_example")],
            [InlineKeyboardButton(text="🔙 К тестам", callback_data="testing")]
        ]),
        parse_mode="HTML"
    )

# Тест на правила
@dp.callback_query(F.data == "rules_test")
async def rules_test(callback: CallbackQuery):
    test_question = (
        "🧠 <b>Тест на правила - Вопрос 1/3</b>\n\n"
        "❓ <b>Что происходит, если мяч полностью пересек "
        "боковую линию?</b>\n\n"
        "Выберите правильный ответ:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A) Угловой удар", callback_data="rules_a_1")],
        [InlineKeyboardButton(text="B) Вбрасывание", callback_data="rules_b_1")],
        [InlineKeyboardButton(text="C) Штрафной удар", callback_data="rules_c_1")],
        [InlineKeyboardButton(text="🔙 К тестам", callback_data="testing")]
    ])
    
    await callback.message.edit_text(test_question, reply_markup=keyboard, parse_mode="HTML")

# Обработка ответов теоретического теста
@dp.callback_query(F.data.in_(["answer_a_1", "answer_b_1", "answer_c_1"]))
async def handle_theory_answer(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if callback.data == "answer_b_1":  # Правильный ответ
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
        [InlineKeyboardButton(text="📝 Следующий вопрос", callback_data="theory_question_2")],
        [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="my_progress")],
        [InlineKeyboardButton(text="🔙 К тестам", callback_data="testing")]
    ])
    
    await callback.message.edit_text(result_text, reply_markup=keyboard, parse_mode="HTML")

# Обработка ответов теста на правила
@dp.callback_query(F.data.in_(["rules_a_1", "rules_b_1", "rules_c_1"]))
async def handle_rules_answer(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if callback.data == "rules_b_1":  # Правильный ответ
        points_earned = 25
        db.add_points(user_id, points_earned)
        
        result_text = (
            "✅ <b>Отлично!</b>\n\n"
            f"🎉 Ты заработал {points_earned} очков!\n\n"
            "Когда мяч полностью пересекает боковую линию, "
            "назначается вбрасывание руками.\n\n"
            "Ты хорошо знаешь правила! ⚽"
        )
    else:
        result_text = (
            "❌ <b>Неправильно</b>\n\n"
            "Правильный ответ: <b>Вбрасывание</b>\n\n"
            "Когда мяч полностью пересекает боковую линию, "
            "игра возобновляется вбрасыванием руками.\n\n"
            "Изучай правила дальше! 📖"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Следующий вопрос", callback_data="rules_question_2")],
        [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="my_progress")],
        [InlineKeyboardButton(text="🔙 К тестам", callback_data="testing")]
    ])
    
    await callback.message.edit_text(result_text, reply_markup=keyboard, parse_mode="HTML")

# Завершение практического задания
@dp.callback_query(F.data == "complete_practical")
async def complete_practical_task(callback: CallbackQuery):
    user_id = callback.from_user.id
    points_earned = 30
    db.add_points(user_id, points_earned)
    
    result_text = (
        "🏆 <b>Практическое задание выполнено!</b>\n\n"
        f"🎉 Отличная работа! Ты заработал {points_earned} очков!\n\n"
        "💪 Жонглирование - отличное упражнение для развития "
        "техники и чувства мяча.\n\n"
        "Продолжай тренироваться каждый день!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚽ Другое задание", callback_data="practical_test")],
        [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="my_progress")],
        [InlineKeyboardButton(text="🔙 К тестам", callback_data="testing")]
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
        "• За демо урок: 10 очков\n"
        "• За правильный ответ в тесте: 20-25 очков\n"
        "• За выполнение практического задания: 30 очков\n"
        "• За покупку курса: +100 бонусных очков\n\n"
        
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
    
    # Получаем статистику из базы данных
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Общее количество пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Общие очки всех пользователей
        cursor.execute("SELECT SUM(total_points) FROM users")
        total_points = cursor.fetchone()[0] or 0
        
        # Количество активных курсов
        cursor.execute("SELECT COUNT(*) FROM courses WHERE is_active = 1")
        active_courses = cursor.fetchone()[0]
        
        # Топ пользователь по очкам
        cursor.execute("SELECT full_name, total_points FROM users ORDER BY total_points DESC LIMIT 1")
        top_user = cursor.fetchone()
        
        conn.close()
        
        stats_text = (
            f"📊 <b>Статистика бота</b>\n\n"
            f"👥 <b>Всего пользователей:</b> {total_users}\n"
            f"📚 <b>Активных курсов:</b> {active_courses}\n"
            f"⭐ <b>Общие очки:</b> {total_points}\n"
        )
        
        if top_user:
            stats_text += f"🏆 <b>Лидер:</b> {top_user[0]} ({top_user[1]} очков)\n"
        
        stats_text += f"\n📈 <i>Статистика обновляется в реальном времени</i>"
        
    except Exception as e:
        stats_text = f"❌ Ошибка получения статистики: {str(e)}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔙 Админ-панель", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(
        stats_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# Добавить заглушки для админских функций
@dp.callback_query(F.data == "admin_add_lesson")
async def admin_add_lesson(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет прав доступа!")
        return
    
    await callback.message.edit_text(
        "➕ <b>Добавление урока</b>\n\n"
        "🚧 Эта функция находится в разработке.\n\n"
        "💡 В следующих версиях здесь будет:\n"
        "• Создание новых уроков\n"
        "• Загрузка видео\n"
        "• Настройка заданий\n"
        "• Управление курсами",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Админ-панель", callback_data="main_menu")
        ]]),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_tasks")
async def admin_tasks(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет прав доступа!")
        return
    
    await callback.message.edit_text(
        "📝 <b>Управление заданиями</b>\n\n"
        "🚧 Эта функция находится в разработке.\n\n"
        "💡 В следующих версиях здесь будет:\n"
        "• Создание тестов и заданий\n"
        "• Редактирование вопросов\n"
        "• Просмотр результатов\n"
        "• Настройка оценок",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Админ-панель", callback_data="main_menu")
        ]]),
        parse_mode="HTML"
    )

# Заглушки для следующих вопросов тестов
@dp.callback_query(F.data == "theory_question_2")
async def theory_question_2(callback: CallbackQuery):
    test_question = (
        "📝 <b>Теоретический тест - Вопрос 2/5</b>\n\n"
        "❓ <b>Какая часть тела НЕ может касаться мяча во время игры "
        "(кроме вратаря в штрафной площади)?</b>\n\n"
        "Выбери правильный ответ:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A) Голова", callback_data="answer2_a")],
        [InlineKeyboardButton(text="B) Руки", callback_data="answer2_b")],
        [InlineKeyboardButton(text="C) Грудь", callback_data="answer2_c")],
        [InlineKeyboardButton(text="🔙 К тестам", callback_data="testing")]
    ])
    
    await callback.message.edit_text(test_question, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(F.data.in_(["answer2_a", "answer2_b", "answer2_c"]))
async def handle_theory_answer_2(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if callback.data == "answer2_b":  # Правильный ответ
        points_earned = 20
        db.add_points(user_id, points_earned)
        
        result_text = (
            "✅ <b>Верно!</b>\n\n"
            f"🎉 Ты заработал {points_earned} очков!\n\n"
            "Руками мяч может касаться только вратарь "
            "в своей штрафной площади.\n\n"
            "Отличное знание правил! ⚽"
        )
    else:
        result_text = (
            "❌ <b>Неправильно</b>\n\n"
            "Правильный ответ: <b>Руки</b>\n\n"
            "Руками мяч может касаться только вратарь "
            "в своей штрафной площади.\n\n"
            "Изучай правила футбола! 📚"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏁 Завершить тест", callback_data="finish_theory_test")],
        [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="my_progress")],
        [InlineKeyboardButton(text="🔙 К тестам", callback_data="testing")]
    ])
    
    await callback.message.edit_text(result_text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(F.data == "rules_question_2")
async def rules_question_2(callback: CallbackQuery):
    test_question = (
        "🧠 <b>Тест на правила - Вопрос 2/3</b>\n\n"
        "❓ <b>Сколько времени длится стандартный футбольный матч?</b>\n\n"
        "Выберите правильный ответ:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A) 80 минут", callback_data="rules2_a")],
        [InlineKeyboardButton(text="B) 90 минут", callback_data="rules2_b")],
        [InlineKeyboardButton(text="C) 100 минут", callback_data="rules2_c")],
        [InlineKeyboardButton(text="🔙 К тестам", callback_data="testing")]
    ])
    
    await callback.message.edit_text(test_question, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(F.data.in_(["rules2_a", "rules2_b", "rules2_c"]))
async def handle_rules_answer_2(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if callback.data == "rules2_b":  # Правильный ответ
        points_earned = 25
        db.add_points(user_id, points_earned)
        
        result_text = (
            "✅ <b>Правильно!</b>\n\n"
            f"🎉 Ты заработал {points_earned} очков!\n\n"
            "Футбольный матч длится 90 минут: "
            "два тайма по 45 минут + компенсированное время.\n\n"
            "Ты отлично знаешь футбол! 🏆"
        )
    else:
        result_text = (
            "❌ <b>Неправильно</b>\n\n"
            "Правильный ответ: <b>90 минут</b>\n\n"
            "Футбольный матч длится 90 минут: "
            "два тайма по 45 минут + компенсированное время.\n\n"
            "Продолжай изучать правила! 📖"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏁 Завершить тест", callback_data="finish_rules_test")],
        [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="my_progress")],
        [InlineKeyboardButton(text="🔙 К тестам", callback_data="testing")]
    ])
    
    await callback.message.edit_text(result_text, reply_markup=keyboard, parse_mode="HTML")

# Завершение тестов
@dp.callback_query(F.data == "finish_theory_test")
async def finish_theory_test(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_points = db.get_user_points(user_id)
    
    final_text = (
        "🏁 <b>Теоретический тест завершен!</b>\n\n"
        f"📊 <b>Твои текущие очки:</b> {user_points}\n"
        f"🎯 Отличная работа! Ты проверил свои теоретические знания.\n\n"
        f"💡 Совет: проходи тесты регулярно, чтобы улучшать результаты!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Пройти снова", callback_data="theory_test")],
        [InlineKeyboardButton(text="⚽ Практические задания", callback_data="practical_test")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(final_text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(F.data == "finish_rules_test")
async def finish_rules_test(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_points = db.get_user_points(user_id)
    
    final_text = (
        "🏁 <b>Тест на правила завершен!</b>\n\n"
        f"📊 <b>Твои текущие очки:</b> {user_points}\n"
        f"🧠 Превосходно! Ты хорошо знаешь правила футбола.\n\n"
        f"⚽ Теперь можешь применить знания на практике!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Пройти снова", callback_data="rules_test")],
        [InlineKeyboardButton(text="📝 Теоретический тест", callback_data="theory_test")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(final_text, reply_markup=keyboard, parse_mode="HTML")

# Показать пример видео
@dp.callback_query(F.data == "show_example")
async def show_video_example(callback: CallbackQuery):
    await callback.message.edit_text(
        "📹 <b>Видео-пример жонглирования</b>\n\n"
        "🎥 В этом видео показаны основы жонглирования:\n"
        "• Правильная постановка ноги\n"
        "• Техника касания мяча\n"
        "• Контроль высоты подброса\n"
        "• Ритм и координация\n\n"
        "💡 <i>Видео-контент будет добавлен администраторами</i>\n\n"
        "🎯 Попробуй повторить движения из видео!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Попробовал, выполнил задание", callback_data="complete_practical")],
            [InlineKeyboardButton(text="🔙 К заданию", callback_data="practical_test")]
        ]),
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
    print(f"🔑 Токен бота: {BOT_TOKEN[:10]}...")
    print(f"👑 Админы: {ADMIN_IDS}")
    
    # Удаляем webhook и запускаем polling
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Бот успешно запущен!")
    print("📱 Отправьте /start для начала работы")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Бот остановлен")
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")