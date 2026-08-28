from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from database.db import db
from keyboards.inline import get_personal_link_kb
from keyboards.reply import get_main_menu_kb

router = Router(name="user_router")
user_router = router

@router.message(CommandStart(deep_link=False))
async def cmd_start_direct(message: Message, state: FSMContext):
    """Обработчик команды /start без параметров (глубоких ссылок)."""
    await state.clear()
    user = message.from_user
    bot_info = await message.bot.get_me()
    is_admin = await db.is_admin(user.id)
    
    personal_link = f"https://t.me/{bot_info.username}?start={user.id}"
    
    text = (
        f"👋 Привет, *{user.first_name}*!\n\n"
        f"🤫 С помощью этого бота ты можешь получать **анонимные сообщения и вопросы** от друзей, подписчиков и знакомых.\n\n"
        f"🔗 **Твоя персональная ссылка:**\n`{personal_link}`\n\n"
        f"📌 *Как пользоваться:*\n"
        f"1. Скопируй ссылку выше или нажми кнопку ниже.\n"
        f"2. Размести её в описании своего профиля (Telegram, Instagram, VK, TikTok) или опубликуй в историях.\n"
        f"3. Получай анонимные вопросы и отвечай на них прямо здесь!"
    )
    
    await message.answer(
        text=text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_kb(is_admin=is_admin)
    )
    
    await message.answer(
        "👇 Нажми, чтобы поделиться ссылкой:",
        reply_markup=get_personal_link_kb(bot_info.username, user.id)
    )

@router.message(F.text == "🔗 Моя ссылка")
async def btn_my_link(message: Message, state: FSMContext):
    """Кнопка 'Моя ссылка' из нижнего меню."""
    await state.clear()
    user = message.from_user
    bot_info = await message.bot.get_me()
    personal_link = f"https://t.me/{bot_info.username}?start={user.id}"
    
    text = (
        f"🔗 **Твоя персональная ссылка для анонимных вопросов:**\n\n"
        f"`{personal_link}`\n\n"
        f"Скопируй её и вставь в описание профиля или отправь друзьям!"
    )
    await message.answer(
        text=text,
        parse_mode="Markdown",
        reply_markup=get_personal_link_kb(bot_info.username, user.id)
    )

@router.message(F.text == "ℹ️ О боте / Инструкция")
async def btn_about(message: Message, state: FSMContext):
    """Информация о боте и инструкция."""
    await state.clear()
    text = (
        f"🤖 *О боте анонимных вопросов*\n\n"
        f"Этот бот позволяет людям писать вам любые сообщения совершенно анонимно.\n\n"
        f"✨ *Возможности:*\n"
        f"• Отправка текста, фото, голосовых сообщений, видео-заметок (кружочков) и стикеров.\n"
        f"• Возможность отвечать на полученные анонимки.\n"
        f"• Полная конфиденциальность для обычных пользователей.\n\n"
        f"⚠️ Пожалуйста, соблюдайте правила приличия и не рассылайте спам/угрозы."
    )
    await message.answer(text=text, parse_mode="Markdown")

@router.message(Command("id"))
async def cmd_id(message: Message):
    """Быстрая команда для получения своего ID."""
    await message.answer(f"🆔 Твой Telegram ID: `{message.from_user.id}`", parse_mode="Markdown")
