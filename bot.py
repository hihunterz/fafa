
import asyncio
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.filters.text import Text
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

import os

DATABASE_URL = os.getenv("DATABASE_URL")
API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Главное меню
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("🔎 Найти объявления")],
        [KeyboardButton("➕ Разместить объявление")],
        [KeyboardButton("👤 Профиль")]
    ],
    resize_keyboard=True
)

# Inline‑кнопки
inline_start = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton("🔎 Найти объявления", callback_data="find_ads")],
    [InlineKeyboardButton("➕ Разместить объявление", callback_data="create_ad")],
    [InlineKeyboardButton("👤 Профиль", callback_data="profile")]
])

# Сессии пользователей
user_sessions = {}

# Подключение к базе
async def create_db_pool():
    return await asyncpg.create_pool(DATABASE_URL)

db_pool = None

# Старт
@dp.message(CommandStart())
async def start(message: types.Message):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (telegram_id, username, name)
            VALUES ($1, $2, $3)
            ON CONFLICT (telegram_id) DO NOTHING
        """, message.from_user.id, message.from_user.username, message.from_user.full_name)
    await message.answer("Добро пожаловать на Биржу Объявлений!", reply_markup=main_menu)
    await message.answer("Выберите действие:", reply_markup=inline_start)

# ➕ Разместить объявление
@dp.message(Text("➕ Разместить объявление"))
async def ask_type(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("📌 Заказ", callback_data="type_order")],
        [InlineKeyboardButton("🧑‍💻 Услуга", callback_data="type_service")]
    ])
    await message.answer("Что хотите разместить?", reply_markup=keyboard)

# Обработка inline
@dp.callback_query()
async def callback_handler(query: types.CallbackQuery):
    uid = query.from_user.id
    async with db_pool.acquire() as conn:
        if query.data == "profile":
            user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id=$1", uid)
            await bot.send_message(uid,
                f"👤 Профиль:\nИмя: {user['name']}\nРейтинг: {user['rating']} ({user['reviews_count']} отзывов)")
            await query.answer()
            return

        if query.data == "find_ads":
            ads = await conn.fetch("SELECT * FROM ads WHERE status='active'")
            if not ads:
                await bot.send_message(uid, "Объявлений пока нет.")
            else:
                for ad in ads:
                    await bot.send_message(uid,
                        f"📌 {ad['title']}\n{ad['description']}\n💰 {ad['price']}\nКатегория: {ad['category']}")
            await query.answer()
            return

        if query.data in ["type_order", "type_service"]:
            ad_type = "order" if query.data=="type_order" else "service"
            user_sessions[uid] = {"type": ad_type}
            await bot.send_message(uid, "Введите категорию (например: Дизайн, IT, Маркетинг):")
            await query.answer()

# Сбор данных объявления
@dp.message()
async def collect_ad_data(message: types.Message):
    uid = message.from_user.id
    if uid not in user_sessions:
        return
    session = user_sessions[uid]

    if "category" not in session:
        session["category"] = message.text
        await message.answer("Введите заголовок:")
    elif "title" not in session:
        session["title"] = message.text
        await message.answer("Введите описание:")
    elif "description" not in session:
        session["description"] = message.text
        await message.answer("Введите цену (например: 5000 ₽):")
    else:
        session["price"] = message.text
        # Сохраняем в базу
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO ads (user_id, type, category, title, description, price, status)
                VALUES ((SELECT id FROM users WHERE telegram_id=$1), $2, $3, $4, $5, $6, 'active')
                RETURNING id
            """, uid, session["type"], session["category"], session["title"], session["description"], session["price"])
            ad_id = row["id"]
        # Публикация в канал
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=(
                f"📌 *{session['title']}*\n"
                f"📝 {session['description']}\n"
                f"💰 {session['price']}\n"
                f"📂 {session['category']}\n"
                f"👤 Автор: {message.from_user.full_name}\n"
                f"🗂 Тип: {session['type']}"
            ),
            parse_mode="Markdown"
        )
        await message.answer("✅ Объявление опубликовано в канале!")
        user_sessions.pop(uid)

# Запуск
async def main():
    global db_pool
    db_pool = await create_db_pool()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())