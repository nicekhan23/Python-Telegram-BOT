from aiogram import types, F, Router, Bot
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
import json
import sqlite3

payments_router = Router()

# Настройки платежей
PAYMENT_PROVIDER_TOKEN = ""  # Получить у @BotFather командой /mybots -> Bot Settings -> Payments

# Создание инвойса
@payments_router.callback_query(F.data.startswith("purchase_"))
async def create_invoice(callback: types.CallbackQuery):
    course_id = callback.data.replace("purchase_", "")
    
    # Получаем информацию о курсе из базы данных
    from database import Database
    from config import DB_PATH
    
    db = Database(DB_PATH)
    courses = db.get_courses()
    
    # Находим нужный курс
    selected_course = None
    for course in courses:
        if str(course[0]) == course_id:
            selected_course = course
            break
    
    if not selected_course:
        await callback.answer("❌ Курс не найден!")
        return
    
    course_id_int, title, description, price = selected_course
    
    # Проверяем, настроены ли платежи
    if not PAYMENT_PROVIDER_TOKEN:
        await callback.message.edit_text(
            "💳 <b>Система оплаты</b>\n\n"
            f"📖 <b>Курс:</b> {title}\n"
            f"📝 <b>Описание:</b> {description}\n"
            f"💰 <b>Цена:</b> {price} руб.\n\n"
            "🔧 <b>Статус:</b> Платежи настраиваются\n\n"
            "💡 <b>Доступные способы:</b>\n"
            "• Тестовая покупка (для демонстрации)\n"
            "• Обращение к администратору\n\n"
            "⚠️ <i>Для настройки реальных платежей нужен токен провайдера</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🧪 Тестовая покупка", callback_data=f"test_purchase_{course_id}")],
                [InlineKeyboardButton(text="💬 Связаться с админом", callback_data="contact_admin")],
                [InlineKeyboardButton(text="🔙 К курсам", callback_data="buy_course")]
            ]),
            parse_mode="HTML"
        )
        return
    
    # Создаем инвойс (если токен настроен)
    prices = [LabeledPrice(label=title, amount=price * 100)]  # в копейках
    
    try:
        await callback.message.bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"Курс: {title}",
            description=description,
            payload=f"course_{course_id}",
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="RUB",
            prices=prices,
            start_parameter=f"course-{course_id}",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            send_phone_number_to_provider=False,
            send_email_to_provider=False,
            is_flexible=False,
        )
        await callback.answer("💳 Инвойс создан!")
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка создания платежа</b>\n\n"
            f"🔧 Подробности: {str(e)}\n\n"
            f"💡 Попробуйте тестовую покупку или обратитесь к администратору",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🧪 Тестовая покупка", callback_data=f"test_purchase_{course_id}")],
                [InlineKeyboardButton(text="🔙 К курсам", callback_data="buy_course")]
            ]),
            parse_mode="HTML"
        )

# Связаться с администратором
@payments_router.callback_query(F.data == "contact_admin")
async def contact_admin(callback: types.CallbackQuery):
    from config import ADMIN_IDS
    
    contact_text = (
        "💬 <b>Связь с администратором</b>\n\n"
        "📞 <b>Способы связи:</b>\n"
        "• Написать в поддержку бота\n"
        "• Обратиться к администратору\n\n"
        f"👑 <b>ID администраторов:</b> {', '.join(map(str, ADMIN_IDS))}\n\n"
        "💡 <i>Администраторы помогут с покупкой курсов и настройкой платежей</i>"
    )
    
    await callback.message.edit_text(
        contact_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К покупкам", callback_data="buy_course")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ]),
        parse_mode="HTML"
    )

# Pre-checkout запрос
@payments_router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    # Здесь можно добавить дополнительные проверки
    await pre_checkout_query.bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# Successful payment
@payments_router.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    payment = message.successful_payment
    
    # Извлекаем ID курса из payload
    payload = payment.invoice_payload
    course_id = payload.replace("course_", "")
    
    # Активируем курс для пользователя
    from database import Database
    from config import DB_PATH
    
    db = Database(DB_PATH)
    user_id = message.from_user.id
    
    # Обновляем подписку пользователя
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET subscription_active = 1, current_course_id = ?
            WHERE user_id = ?
        ''', (course_id, user_id))
        conn.commit()
        conn.close()
        
        # Добавляем бонусные очки за покупку
        db.add_points(user_id, 100)
        
        success_text = (
            f"🎉 <b>Платеж успешно выполнен!</b>\n\n"
            f"💰 <b>Сумма:</b> {payment.total_amount // 100} {payment.currency}\n"
            f"🆔 <b>ID транзакции:</b> {payment.telegram_payment_charge_id}\n\n"
            f"✅ Курс активирован!\n"
            f"🎁 <b>Бонус:</b> +100 очков\n\n"
            f"📚 Теперь вы можете приступить к обучению!"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 Мои курсы", callback_data="my_courses")],
            [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="my_progress")]
        ])
        
        await message.answer(success_text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(
            f"✅ Платеж получен, но возникла ошибка при активации курса.\n"
            f"Обратитесь к администратору.\n\nОшибка: {str(e)}"
        )

# Тестовая покупка (для разработки)
@payments_router.callback_query(F.data.startswith("test_purchase_"))
async def test_purchase(callback: types.CallbackQuery):
    """Тестовая покупка для разработки"""
    course_id = callback.data.replace("test_purchase_", "")
    user_id = callback.from_user.id
    
    # Получаем информацию о курсе
    from database import Database
    from config import DB_PATH
    
    db = Database(DB_PATH)
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
    
    # Имитируем успешную покупку
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET subscription_active = 1, current_course_id = ?
            WHERE user_id = ?
        ''', (course_id, user_id))
        conn.commit()
        conn.close()
        
        # Добавляем бонусные очки
        db.add_points(user_id, 100)
        
        await callback.message.edit_text(
            f"🧪 <b>ТЕСТОВАЯ ПОКУПКА ЗАВЕРШЕНА</b>\n\n"
            f"📖 <b>Курс:</b> {title}\n"
            f"💰 <b>Цена:</b> {price} руб. (не списана)\n"
            f"✅ <b>Статус:</b> Активирован\n"
            f"🎁 <b>Бонус:</b> +100 очков\n\n"
            f"⚠️ <i>Это демонстрация функционала для разработки</i>\n"
            f"💡 Реальные платежи требуют настройки с провайдером",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📖 Перейти к курсу", callback_data=f"course_{course_id}")],
                [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="my_progress")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка тестовой покупки</b>\n\n"
            f"🔧 Подробности: {str(e)}\n\n"
            f"💡 Обратитесь к администратору",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К курсам", callback_data="buy_course")]
            ]),
            parse_mode="HTML"
        )

# Инструкции по настройке платежей (для администраторов)
@payments_router.callback_query(F.data == "payment_setup_info")
async def payment_setup_info(callback: types.CallbackQuery):
    from config import ADMIN_IDS
    
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Только для администраторов!")
        return
    
    setup_text = (
        "💳 <b>Настройка платежей Telegram</b>\n\n"
        
        "<b>Шаг 1: Получение токена</b>\n"
        "1. Найдите @BotFather в Telegram\n"
        "2. Отправьте команду /mybots\n"
        "3. Выберите вашего бота\n"
        "4. Bot Settings → Payments\n"
        "5. Подключите платежного провайдера\n\n"
        
        "<b>Популярные провайдеры:</b>\n"
        "• ЮKassa (Россия) 🇷🇺\n"
        "• Stripe (международный) 🌍\n"
        "• Сбербанк (Россия) 🏦\n"
        "• PayPal 💳\n\n"
        
        "<b>Шаг 2: Добавление токена</b>\n"
        "В файле <code>payments.py</code> укажите:\n"
        "<code>PAYMENT_PROVIDER_TOKEN = 'ваш_токен'</code>\n\n"
        
        "⚠️ <b>Важно:</b>\n"
        "• Для тестов используйте TEST токены\n"
        "• Проверьте валюту (RUB/USD/EUR)\n"
        "• Настройте webhook для продакшена\n\n"
        
        "📞 При проблемах обращайтесь в поддержку провайдера"
    )
    
    await callback.message.edit_text(
        setup_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
        ]),
        parse_mode="HTML"
    )

def get_payment_setup_instructions():
    """Возвращает инструкции по настройке платежей"""
    return (
        "💳 <b>Настройка платежей Telegram</b>\n\n"
        
        "<b>Шаг 1:</b> Получение токена\n"
        "1. Найдите @BotFather в Telegram\n"
        "2. Отправьте команду /mybots\n"
        "3. Выберите вашего бота\n"
        "4. Bot Settings → Payments\n"
        "5. Подключите платежного провайдера\n\n"
        
        "<b>Доступные провайдеры:</b>\n"
        "• ЮKassa (для России)\n"
        "• Stripe (международные)\n"
        "• PayPal\n"
        "• Сбербанк\n\n"
        
        "<b>Шаг 2:</b> Добавление токена\n"
        "В файле config.py укажите:\n"
        "<code>PAYMENT_PROVIDER_TOKEN = '2051251535:TEST:OTk5MDA4ODgxLTAwNQ'</code>\n\n"
        
        "⚠️ <b>Важно:</b> Для тестирования используйте тестовые токены!"
    )