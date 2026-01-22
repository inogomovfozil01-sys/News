import asyncio
import sqlite3
from datetime import datetime
import pytz
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.enums import ContentType

TOKEN = "8541200501:AAEI_0KYbZu3wV8WKWGQ7rUKJlQJP2IvYLI"
ADMIN_IDS = [6690476979]

tz = pytz.timezone("Europe/Moscow")

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

db = sqlite3.connect("users.db", check_same_thread=False)
cursor = db.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    first_name TEXT
)
""")
db.commit()

def add_user(user_id: int, first_name: str):
    if user_id in ADMIN_IDS:
        return
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, first_name) VALUES (?, ?)",
        (user_id, first_name)
    )
    db.commit()

def get_users():
    cursor.execute("SELECT user_id, first_name FROM users")
    return cursor.fetchall()

waiting_for_post = False
waiting_for_datetime = False
saved_message = None

admin_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="publish")]]
)

confirm_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🚀 Отправить сейчас", callback_data="send_now"),
            InlineKeyboardButton(text="⏰ Запланировать", callback_data="delay")
        ],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel")]
    ]
)

@router.message(Command("start"))
async def start(message: types.Message):
    add_user(message.from_user.id, message.from_user.first_name)
    if message.from_user.id in ADMIN_IDS:
        await message.answer("Панель администратора:", reply_markup=admin_keyboard)
    else:
        await message.answer("Вы успешно подписались ✅")

@router.callback_query(lambda c: c.data == "publish")
async def publish(callback: types.CallbackQuery):
    global waiting_for_post
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return
    waiting_for_post = True
    await callback.message.answer("✍️ Отправьте сообщение для рассылки")
    await callback.answer()

@router.message()
async def catch_message(message: types.Message):
    global waiting_for_post, saved_message
    if message.from_user.id not in ADMIN_IDS or not waiting_for_post:
        return
    waiting_for_post = False
    saved_message = message
    await bot.copy_message(
        chat_id=message.from_user.id,
        from_chat_id=message.chat.id,
        message_id=message.message_id
    )
    await message.answer("👆 Предпросмотр\nВыберите действие:", reply_markup=confirm_keyboard)

@router.callback_query(lambda c: c.data == "send_now")
async def send_now(callback: types.CallbackQuery):
    await send_to_all()
    await callback.answer()

@router.callback_query(lambda c: c.data == "delay")
async def delay(callback: types.CallbackQuery):
    global waiting_for_datetime
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return
    waiting_for_datetime = True
    await callback.message.answer("Введите дату и время по МСК:\n22.01.2026 13:00")
    await callback.answer()

@router.message()
async def get_datetime(message: types.Message):
    global waiting_for_datetime
    if not waiting_for_datetime or message.from_user.id not in ADMIN_IDS:
        return
    try:
        naive_dt = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        target_time = tz.localize(naive_dt)
        now = datetime.now(tz)

        delay_seconds = (target_time - now).total_seconds()
        if delay_seconds <= 0:
            await message.answer("Время уже прошло. Введите будущее время по МСК.")
            return

        waiting_for_datetime = False
        await message.answer(f"⏳ Рассылка запланирована на {message.text} по МСК")
        asyncio.create_task(delayed_send(delay_seconds))

    except:
        await message.answer("Неверный формат. Пример: 22.01.2026 13:00")

async def delayed_send(seconds):
    await asyncio.sleep(seconds)
    await send_to_all()

async def send_to_all():
    global saved_message
    if not saved_message:
        return

    users = get_users()
    sent = 0
    failed = 0

    for user_id, first_name in users:
        try:
            greeting = (
                f"👋 Привет, {first_name}!\n"
                f"Тебе поступили новые новости проекта, советую прочитать ниже:\n\n"
            )

            ct = saved_message.content_type

            if ct == ContentType.TEXT:
                await bot.send_message(user_id, greeting + saved_message.text)

            elif ct == ContentType.PHOTO:
                await bot.send_photo(
                    user_id,
                    saved_message.photo[-1].file_id,
                    caption=greeting + (saved_message.caption or "")
                )

            elif ct == ContentType.VIDEO:
                await bot.send_video(
                    user_id,
                    saved_message.video.file_id,
                    caption=greeting + (saved_message.caption or "")
                )

            elif ct == ContentType.DOCUMENT:
                await bot.send_document(
                    user_id,
                    saved_message.document.file_id,
                    caption=greeting + (saved_message.caption or "")
                )

            sent += 1

        except:
            failed += 1

    saved_message = None

    summary = f"✅ Рассылка завершена\nОтправлено: {sent}\nОшибок: {failed}"
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, summary, reply_markup=admin_keyboard)

@router.callback_query(lambda c: c.data == "cancel")
async def cancel(callback: types.CallbackQuery):
    global saved_message, waiting_for_datetime
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return
    saved_message = None
    waiting_for_datetime = False
    await callback.message.answer("❌ Рассылка отменена", reply_markup=admin_keyboard)
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
