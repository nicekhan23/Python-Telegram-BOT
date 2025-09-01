from aiogram import types, F, Router
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
import json

payments_router = Router()

# Настройки платежей
PAYMENT_PROVIDER_TOKEN = ""  # Получить у @BotFather командой /mybots -> Bot Settings -> Payments

# Создание инвойса
@payments_router.callback_query(F.data.startswith("purchase_"))
async def create_invoice(callback: types.CallbackQuery, bot):
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
            "💳 <b>Платежи временно недоступны</b>\n\n"
            "🔧 Администратор настраивает платежную систему.\n"
            "Попробуйте позже или обратитесь в поддержку.\n\n"
            f"📖 <b>Курс:</b> {title}\n"
            f"💰 <b>Цена:</b> {price} руб.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 К курсам", callback_data="buy_course")
            ]]),
            parse_mode="HTML"
        )
        return
    
    # Создаем инвойс
    prices = [LabeledPrice(label=title, amount=price * 100)]  # в копейках
    
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"Курс: {title}",
        description=description,
        payload=f"course_{course_id}",
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency="RUB",
        prices=prices,
        start_parameter=f"course-{course_id}",
        photo_url="https://example.com/course-image.jpg",  # Опционально
        photo_size=512,
        photo_width=512,
        photo_height=512,
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        send_phone_number_to_provider=False,
        send_email_to_provider=False,
        is_flexible=False,
    )
    
    await callback.answer("💳 Инвойс создан!")

# Pre-checkout запрос
@payments_router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery, bot):
    # Здесь можно добавить дополнительные проверки
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

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
    conn = db.get_connection() if hasattr(db, 'get_connection') else None
    if conn:
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

# Альтернативная система оплаты (для тестирования)
@payments_router.callback_query(F.data.startswith("test_purchase_"))
async def test_purchase(callback: types.CallbackQuery):
    """Тестовая покупка для разработки"""
    course_id = callback.data.replace("test_purchase_", "")
    user_id = callback.from_user.id
    
    # Имитируем успешную покупку
    from database import Database
    from config import DB_PATH
    
    db = Database(DB_PATH)
    db.add_points(user_id, 100)
    
    await callback.message.edit_text(
        f"🧪 <b>ТЕСТОВАЯ ПОКУПКА</b>\n\n"
        f"✅ Курс #{course_id} активирован\n"
        f"🎁 Получено: +100 очков\n\n"
        f"⚠️ <i>Это тестовый режим для разработки</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 Мои курсы", callback_data="my_courses")]
        ]),
        parse_mode="HTML"
    )

# Инструкции по настройке платежей
def get_payment_setup_instructions():
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