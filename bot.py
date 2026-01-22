import asyncio
import os
import sqlite3
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.enums import ContentType

TOKEN = "8541200501:AAEI_0KYbZu3wV8WKWGQ7rUKJlQJP2IvYLI"
ADMIN_IDS = [6690476979]

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
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, first_name) VALUES (?, ?)",
        (user_id, first_name)
    )
    db.commit()

def get_users():
    cursor.execute("SELECT user_id, first_name FROM users")
    return cursor.fetchall()

waiting_for_post = False
waiting_for_delay = False
saved_message = None

admin_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="publish")]]
)

confirm_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🚀 Отправить сейчас", callback_data="send_now"),
            InlineKeyboardButton(text="⏱ Отложить", callback_data="delay")
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

@router.message(Command("chat"))
async def chat_command(message: types.Message):
    add_user(message.from_user.id, message.from_user.first_name)
    file_path = "photo_2025-12-13_16-31-07.jpg"
    text = (
        "Привет! Вы выбрали команду /chat!\n\n"
        "Ниже кнопка для перехода в чат с администрацией проекта."
    )
    chat_button = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Перейти в чат 🌐", url="https://t.me/VolnaBot_bot")]]
    )
    file = FSInputFile(file_path)
    await bot.send_photo(message.chat.id, file, caption=text, reply_markup=chat_button)

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
    await send_to_all(callback)

@router.callback_query(lambda c: c.data == "delay")
async def delay(callback: types.CallbackQuery):
    global waiting_for_delay
    waiting_for_delay = True
    await callback.message.answer("⏱ Введите задержку в минутах")
    await callback.answer()

@router.message()
async def get_delay(message: types.Message):
    global waiting_for_delay
    if not waiting_for_delay:
        return
    if not message.text.isdigit():
        await message.answer("Введите число")
        return
    waiting_for_delay = False
    minutes = int(message.text)
    await message.answer(f"⏳ Рассылка будет через {minutes} минут")
    asyncio.create_task(delayed_send(minutes * 60))

async def delayed_send(seconds):
    await asyncio.sleep(seconds)
    await send_to_all()

async def send_to_all(callback=None):
    global saved_message
    if not saved_message:
        return
    users = get_users()
    sent = 0
    failed = 0
    for user_id, first_name in users:
        try:
            greeting = f"👋 Привет, {first_name}!\n\n"
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
    global saved_message, waiting_for_delay
    saved_message = None
    waiting_for_delay = False
    await callback.message.answer("❌ Рассылка отменена", reply_markup=admin_keyboard)
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
