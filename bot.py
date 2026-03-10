import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Float, Text, select, update

# ===== Настройки =====
TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(TOKEN)
dp = Dispatcher()

# ===== PostgreSQL и ORM =====
Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

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
        [InlineKeyboardButton(text="➕ Разместить объявление", callback_data="create_ad")],
        [InlineKeyboardButton(text="📋 Все объявления", callback_data="all_ads")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")]
    ])
    await message.answer("Добро пожаловать на биржу объявлений 🚀", reply_markup=keyboard)

# ===== Создание объявления =====
@dp.callback_query(lambda c: c.data=="create_ad")
async def create_ad(cb: types.CallbackQuery):
    user_state[cb.from_user.id] = {"step":"title"}
    await cb.message.answer("Введите заголовок объявления")

@dp.message()
async def process_state(message: types.Message):
    if message.from_user.id not in user_state:
        return
    state = user_state[message.from_user.id]

    async with async_session() as session:
        if state["step"]=="title":
            state["title"] = message.text
            state["step"] = "desc"
            await message.answer("Введите описание")
            return

        if state["step"]=="desc":
            state["desc"] = message.text
            state["step"] = "price"
            await message.answer("Введите цену")
            return

        if state["step"]=="price":
            ad = Ad(
                user_id=message.from_user.id,
                title=state["title"],
                description=state["desc"],
                price=message.text
            )
            session.add(ad)
            await session.commit()

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Откликнуться", callback_data=f"respond_{ad.id}")]
            ])

            text = f"📢 {ad.title}\n\n{ad.description}\n\n💰 {ad.price}"
            await bot.send_message(CHANNEL_ID, text, reply_markup=keyboard)
            await message.answer("Объявление опубликовано в канале ✅")
            user_state.pop(message.from_user.id)

# ===== Просмотр всех объявлений =====
@dp.callback_query(lambda c: c.data=="all_ads")
async def all_ads(cb: types.CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(Ad, User.username).join(User, User.telegram_id==Ad.user_id).where(Ad.status=="open")
        )
        rows = result.all()

    if not rows:
        await cb.message.answer("Нет объявлений")
        return

    text = "📋 Объявления:\n\n"
    for ad, username in rows:
        text += f"{ad.id} | @{username} | {ad.title} | {ad.price}\n"
    await cb.message.answer(text)

# ===== Отклики =====
@dp.callback_query(lambda c: c.data.startswith("respond_"))
async def respond(cb: types.CallbackQuery):
    ad_id=int(cb.data.split("_")[1])
    user_state[cb.from_user.id]={"step":"respond","ad":ad_id}
    await cb.message.answer("Напишите ваше предложение")

@dp.message()
async def process_response(message: types.Message):
    if message.from_user.id not in user_state:
        return
    state=user_state[message.from_user.id]
    if state["step"]!="respond":
        return
    ad_id=state["ad"]
    async with async_session() as session:
        response = Response(ad_id=ad_id, responder_id=message.from_user.id, message=message.text)
        session.add(response)
        await session.commit()
        # Отправка владельцу объявления
        result = await session.execute(select(Ad).where(Ad.id==ad_id))
        ad = result.scalar()
        if ad:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🤝 Принять", callback_data=f"deal_{ad_id}_{message.from_user.id}")]
            ])
            await bot.send_message(ad.user_id, f"Отклик на '{ad.title}':\n\n{message.text}", reply_markup=keyboard)
    await message.answer("Отклик отправлен")
    user_state.pop(message.from_user.id)

# ===== Сделка =====
@dp.callback_query(lambda c: c.data.startswith("deal_"))
async def deal(cb: types.CallbackQuery):
    parts = cb.data.split("_")
    ad_id = int(parts[1])
    freelancer = int(parts[2])
    async with async_session() as session:
        await session.execute(update(Ad).where(Ad.id==ad_id).values(status="closed"))
        await session.commit()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data=f"review_{freelancer}")]
    ])
    await bot.send_message(cb.from_user.id,"Сделка завершена",reply_markup=keyboard)

# ===== Отзыв =====
@dp.callback_query(lambda c: c.data.startswith("review_"))
async def review(cb: types.CallbackQuery):
    user_state[cb.from_user.id]={"step":"rating","target":int(cb.data.split("_")[1])}
    await cb.message.answer("Оцените исполнителя от 1 до 5")

@dp.message()
async def rating(message: types.Message):
    if message.from_user.id not in user_state:
        return
    state = user_state[message.from_user.id]
    if state["step"]!="rating":
        return
    rating_value = int(message.text)
    target = state["target"]
    async with async_session() as session:
        review = Review(from_user=message.from_user.id, to_user=target, rating=rating_value, comment="")
        session.add(review)
        # Обновляем рейтинг
        result = await session.execute(select(User).where(User.telegram_id==target))
        user = result.scalar()
        if user:
            new_rating = ((user.rating*user.reviews_count)+rating_value)/(user.reviews_count+1)
            user.rating=new_rating
            user.reviews_count+=1
            session.add(user)
        await session.commit()
    await message.answer("Спасибо за отзыв ⭐")
    user_state.pop(message.from_user.id)

# ===== Профиль =====
@dp.callback_query(lambda c: c.data=="profile")
async def profile(cb: types.CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id==cb.from_user.id))
        user = result.scalar()
    if user:
        await cb.message.answer(f"👤 Профиль\n⭐ Рейтинг: {user.rating:.2f}\nОтзывы: {user.reviews_count}")

# ===== Запуск бота =====
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())