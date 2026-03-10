import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Float, Text, select

# ===== Настройки =====
TOKEN = os.getenv("API_TOKEN")  # Telegram Bot Token
CHANNEL_ID = os.getenv("CHANNEL_ID")  # канал для публикаций
DATABASE_URL = "sqlite+aiosqlite:///./freelance_db.sqlite"  # локальный SQLite

bot = Bot(TOKEN)
dp = Dispatcher()

Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# ===== Модели =====
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    username = Column(String(100))
    name = Column(String(100))
    rating = Column(Float, default=0)
    reviews_count = Column(Integer, default=0)

class Ad(Base):
    __tablename__ = "ads"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    title = Column(String(200))
    description = Column(Text)
    price = Column(String(50))
    status = Column(String(20), default="open")

class Response(Base):
    __tablename__ = "responses"
    id = Column(Integer, primary_key=True)
    ad_id = Column(Integer)
    responder_id = Column(Integer)
    message = Column(Text)

class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True)
    from_user = Column(Integer)
    to_user = Column(Integer)
    rating = Column(Integer)
    comment = Column(Text)

user_state = {}

# ===== Инициализация базы =====
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ===== /start =====
@dp.message(CommandStart())
async def start(message: types.Message):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar()
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                name=message.from_user.full_name
            )
            session.add(user)
            await session.commit()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("➕ Разместить объявление", callback_data="create_ad")],
        [InlineKeyboardButton("📋 Все объявления", callback_data="all_ads")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")]
    ])
    await message.answer("Добро пожаловать на биржу объявлений 🚀", reply_markup=keyboard)

# ===== Остальной функционал =====
# Можно добавить обработку callback_data для создания объявлений,
# просмотра всех объявлений, откликов, рейтинга и профиля

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())