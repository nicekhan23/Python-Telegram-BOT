from aiogram import types, F, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import Database
from config import ADMIN_IDS

video_router = Router()

# Обработка видео от админа
@video_router.message(F.video)
async def handle_video_upload(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("❌ Только администраторы могут загружать видео!")
        return
    
    video_file_id = message.video.file_id
    video_duration = message.video.duration
    video_size = message.video.file_size
    
    # Сохраняем информацию о видео
    response_text = (
        f"📹 <b>Видео получено!</b>\n\n"
        f"🆔 <b>File ID:</b> <code>{video_file_id}</code>\n"
        f"⏱ <b>Длительность:</b> {video_duration} сек.\n"
        f"💾 <b>Размер:</b> {video_size // 1024 // 1024} МБ\n\n"
        f"💡 <i>Используйте File ID для добавления в урок</i>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать урок с этим видео", 
                            callback_data=f"create_lesson_{video_file_id}")]
    ])
    
    await message.reply(response_text, reply_markup=keyboard, parse_mode="HTML")

# Создание урока с видео
@video_router.callback_query(F.data.startswith("create_lesson_"))
async def create_lesson_with_video(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    
    video_file_id = callback.data.replace("create_lesson_", "")
    
    # Здесь можно добавить FSM для создания урока
    await callback.message.edit_text(
        f"📝 <b>Создание урока</b>\n\n"
        f"Видео: <code>{video_file_id}</code>\n\n"
        f"💡 <i>Функция создания уроков будет добавлена в следующих версиях</i>",
        parse_mode="HTML"
    )

# Показ видео урока пользователю
async def show_lesson_video(bot, chat_id: int, lesson_id: int, db: Database):
    """Функция для показа видео урока пользователю"""
    # Получаем информацию об уроке из базы данных
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT title, description, video_file_id, points_reward 
        FROM lessons WHERE id = ?
    ''', (lesson_id,))
    
    lesson = cursor.fetchone()
    conn.close()
    
    if not lesson:
        await bot.send_message(chat_id, "❌ Урок не найден!")
        return
    
    title, description, video_file_id, points = lesson
    
    if not video_file_id:
        await bot.send_message(
            chat_id, 
            f"📚 <b>{title}</b>\n\n{description}\n\n❌ Видео пока недоступно",
            parse_mode="HTML"
        )
        return
    
    # Отправляем видео
    caption = (
        f"🎥 <b>{title}</b>\n\n"
        f"{description}\n\n"
        f"⭐ <b>За просмотр:</b> +{points} очков"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Урок пройден", 
                            callback_data=f"complete_lesson_{lesson_id}")],
        [InlineKeyboardButton(text="🔙 К курсу", callback_data="my_courses")]
    ])
    
    await bot.send_video(
        chat_id=chat_id,
        video=video_file_id,
        caption=caption,
        reply_markup=keyboard,
        parse_mode="HTML"
    )