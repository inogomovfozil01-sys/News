import asyncio
import sqlite3
from datetime import datetime
import pytz
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8541200501:AAEI_0KYbZu3wV8WKWGQ7rUKJlQJP2IvYLI"
ADMIN_IDS = [6690476979, 7375441296]
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
saved_message: types.Message | None = None
post_sent = False

admin_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="publish")]
    ]
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
        await message.answer("Вы подписались на новости проекта ✅")

@dp.message(Command("chat"))
async def chat_command(message: types.Message):
    add_user(message.from_user.id, message.from_user.first_name)
    file_path = "photo_2025-12-13_16-31-07.jpg"
    text = "Привет! Вы выбрали команду /chat!\nНиже есть кнопка которая поможет вам перейти в чат с администрацией, нашего проекта!\n\n ✅Нажмите и напишите свой вопрос и вам помогут!"
    chat_button = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Перейти в чат 🌐", url="https://t.me/VolnaBot_bot")]]
    )
    file = FSInputFile(file_path)
    await bot.send_photo(chat_id=message.chat.id, photo=file, caption=text, reply_markup=chat_button)


@router.callback_query(lambda c: c.data == "publish")
async def publish(callback: types.CallbackQuery):
    global waiting_for_post, saved_message, post_sent
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return
    saved_message = None
    post_sent = False
    waiting_for_post = True
    await callback.message.answer("✍️ Отправь сообщение для рассылки")
    await callback.answer()

@router.message()
async def admin_flow(message: types.Message):
    global waiting_for_post, waiting_for_datetime, saved_message

    if message.from_user.id not in ADMIN_IDS:
        return

    if waiting_for_post:
        waiting_for_post = False
        saved_message = message
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
        await message.answer("Выбери действие:", reply_markup=confirm_keyboard)
        return

    if waiting_for_datetime:
        try:
            naive_dt = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
            target_time = tz.localize(naive_dt)
            now = datetime.now(tz)
            delay_seconds = (target_time - now).total_seconds()
            if delay_seconds <= 0:
                await message.answer("Время уже прошло. Введи будущее.")
                return
            waiting_for_datetime = False
            await message.answer(f"Рассылка запланирована на {message.text}")
            asyncio.create_task(delayed_send(delay_seconds))
        except:
            await message.answer("Неверный формат. Пример: 22.01.2026 13:00")

@router.callback_query(lambda c: c.data == "send_now")
async def send_now(callback: types.CallbackQuery):
    if post_sent:
        await callback.answer("❗ Этот пост уже отправлен", show_alert=True)
        return
    await send_to_all()
    await callback.answer()

@router.callback_query(lambda c: c.data == "delay")
async def delay(callback: types.CallbackQuery):
    global waiting_for_datetime
    if post_sent:
        await callback.answer("❗ Этот пост уже отправлен", show_alert=True)
        return
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return
    waiting_for_datetime = True
    await callback.message.answer("Введи дату и время по МСК:\n22.01.2026 13:00")
    await callback.answer()

@router.callback_query(lambda c: c.data == "cancel")
async def cancel(callback: types.CallbackQuery):
    global saved_message, waiting_for_datetime, waiting_for_post
    if post_sent:
        await callback.answer("❗ Этот пост уже отправлен", show_alert=True)
        return
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return
    saved_message = None
    waiting_for_datetime = False
    waiting_for_post = False
    await callback.message.answer("Рассылка отменена", reply_markup=admin_keyboard)
    await callback.answer()

async def delayed_send(seconds: float):
    await asyncio.sleep(seconds)
    await send_to_all()

async def send_to_all():
    global saved_message, post_sent
    if not saved_message or post_sent:
        return

    users = get_users()
    sent = 0
    failed = 0

    for user_id, _ in users:
        if user_id in ADMIN_IDS:
            continue
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=saved_message.chat.id,
                message_id=saved_message.message_id
            )
            sent += 1
        except:
            failed += 1

    post_sent = True

    summary = f"Отправлено: {sent}\nОшибок: {failed}"
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, summary, reply_markup=admin_keyboard)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


