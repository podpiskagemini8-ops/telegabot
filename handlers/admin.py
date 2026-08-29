import asyncio
import config
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database.db import db
from keyboards.inline import (
    get_admin_main_kb,
    get_admin_back_kb,
    get_cancel_kb,
    get_banned_list_kb,
    get_gemini_menu_kb,
    get_gemini_chats_list_kb,
    get_gemini_chat_view_kb,
    get_gemini_reply_kb,
    get_gemini_confirm_delete_kb
)
from services.gemini_ai import ask_gemini, GeminiError

router = Router(name="admin_router")
admin_router = router

class AdminStates(StatesGroup):
    waiting_for_broadcast_msg = State()
    confirm_broadcast = State()
    waiting_for_ban_id = State()
    waiting_for_gemini_prompt = State()

@router.message(Command("admin"))
@router.message(F.text == "⚡ Админ-панель")
async def cmd_admin_panel(message: Message, state: FSMContext):
    """Главная страница админ-панели."""
    await state.clear()
    user_id = message.from_user.id

    if not await db.is_admin(user_id):
        await message.answer("⛔ *У вас нет доступа к панели администратора.*", parse_mode="Markdown")
        return

    is_super = (user_id == config.SUPER_ADMIN_ID)
    title = "👑 *ПАНЕЛЬ ГЛАВНОГО АДМИНИСТРАТОРА*" if is_super else "👑 *ПАНЕЛЬ АДМИНИСТРАТОРА*"

    text = (
        f"{title}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Выберите действие ниже:"
    )

    await message.answer(text, parse_mode="Markdown", reply_markup=get_admin_main_kb(is_super_admin=is_super))

@router.callback_query(F.data == "admin_main")
async def callback_admin_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню админки по кнопке."""
    await state.clear()
    user_id = callback.from_user.id
    if not await db.is_admin(user_id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    is_super = (user_id == config.SUPER_ADMIN_ID)
    title = "👑 *ПАНЕЛЬ ГЛАВНОГО АДМИНИСТРАТОРА*" if is_super else "👑 *ПАНЕЛЬ АДМИНИСТРАТОРА*"

    text = (
        f"{title}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Выберите действие ниже:"
    )

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_admin_main_kb(is_super_admin=is_super))

# --- ЛОГИ СООБЩЕНИЙ ---

@router.callback_query(F.data == "admin_recent_msgs")
async def callback_admin_recent_msgs(callback: CallbackQuery):
    """Просмотр последних сообщений (только свои для второго админа, все — для супер-админа)."""
    user_id = callback.from_user.id
    if not await db.is_admin(user_id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    if user_id == config.SUPER_ADMIN_ID:
        recent_msgs = await db.get_recent_messages(limit=8)
    else:
        recent_msgs = await db.get_user_recent_messages(user_id, limit=8)

    if not recent_msgs:
        await callback.message.edit_text("📜 *История сообщений пока пуста.*", parse_mode="Markdown", reply_markup=get_admin_back_kb())
        return

    title = "📜 *ВСЕ ПОСЛЕДНИЕ СООБЩЕНИЯ В БОТЕ:*\n" if user_id == config.SUPER_ADMIN_ID else "📜 *ПОСЛЕДНИЕ СООБЩЕНИЯ, НАПИСАННЫЕ ВАМ:*\n"
    text_parts = [title]
    for m in recent_msgs:
        s_user = f"@{m['sender_username']}" if m.get("sender_username") else f"ID:{m['sender_id']}"
        preview = (m["content"][:35] + "...") if m["content"] and len(m["content"]) > 35 else (m["content"] or "-")

        if user_id == config.SUPER_ADMIN_ID:
            r_user = f"@{m['recipient_username']}" if m.get("recipient_username") else f"ID:{m['recipient_id']}"
            text_parts.append(
                f"🔹 *#{m['id']}* `{m['created_at']}`\n"
                f"От: `{s_user}` ➡️ Кому: `{r_user}`\n"
                f"Тип: _{m['message_type']}_ | _{preview}_\n"
            )
        else:
            text_parts.append(
                f"🔹 *#{m['id']}* `{m['created_at']}`\n"
                f"Отправитель: `{s_user}`\n"
                f"Тип: _{m['message_type']}_ | _{preview}_\n"
            )

    await callback.message.edit_text("\n".join(text_parts), parse_mode="Markdown", reply_markup=get_admin_back_kb())

# --- РАССЫЛКА ---

@router.callback_query(F.data == "admin_broadcast")
async def callback_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    """Запрос сообщения для рассылки."""
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_broadcast_msg)
    await callback.message.edit_text(
        "📢 *Введите сообщение для рассылки по всем пользователям бота.*\n\n"
        "Поддерживаются текст, фото, видео, голосовые, стикеры и кнопки.",
        parse_mode="Markdown",
        reply_markup=get_cancel_kb()
    )

@router.message(AdminStates.waiting_for_broadcast_msg)
async def process_broadcast_content(message: Message, state: FSMContext):
    """Предпросмотр сообщения для рассылки и запрос подтверждения."""
    await state.update_data(broadcast_msg_id=message.message_id, from_chat_id=message.chat.id)
    await state.set_state(AdminStates.confirm_broadcast)

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚀 Начать рассылку", callback_data="start_broadcast_now"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")
        ]
    ])

    await message.reply(
        "⚠️ *Подтверждение рассылки*\n\n"
        "Вы действительно хотите отправить это сообщение всем пользователям бота?",
        parse_mode="Markdown",
        reply_markup=confirm_kb
    )

@router.callback_query(F.data == "start_broadcast_now", AdminStates.confirm_broadcast)
async def callback_start_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Выполнение рассылки всем пользователям."""
    data = await state.get_data()
    msg_id = data.get("broadcast_msg_id")
    chat_id = data.get("from_chat_id")
    await state.clear()

    if not msg_id or not chat_id:
        await callback.answer("❌ Ошибка данных рассылки.", show_alert=True)
        return

    await callback.message.edit_text("⏳ *Рассылка запущена... Пожалуйста, подождите.*", parse_mode="Markdown")

    users = await db.get_all_users()
    total = len(users)
    success = 0
    errors = 0

    for user in users:
        target_id = user["user_id"]
        try:
            await bot.copy_message(
                chat_id=target_id,
                from_chat_id=chat_id,
                message_id=msg_id
            )
            success += 1
            await asyncio.sleep(0.05)  # Защита от лимитов Telegram FloodWait
        except Exception:
            errors += 1

    result_text = (
        f"📢 *РАССЫЛКА ЗАВЕРШЕНА!*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Всего адресатов: *{total}*\n"
        f"✅ Успешно доставлено: *{success}*\n"
        f"❌ Ошибок (заблокировали бота): *{errors}*\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await callback.message.edit_text(result_text, parse_mode="Markdown", reply_markup=get_admin_back_kb())

# --- ЗАБЛОКИРОВАННЫЕ ПОЛЬЗОВАТЕЛИ И РАЗБАН ---

@router.callback_query(F.data == "admin_banned_list")
async def callback_admin_banned_list(callback: CallbackQuery):
    """Список заблокированных пользователей с кнопками мгновенной разблокировки."""
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    banned_list = await db.get_banned_users()
    if not banned_list:
        text = (
            "✅ *Список заблокированных пользователей пуст.*\n\n"
            "В боте нет заблокированных пользователей."
        )
        empty_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Заблокировать по ID", callback_data="admin_ban_menu")],
            [InlineKeyboardButton(text="◀️ Назад в админ-панель", callback_data="admin_main")]
        ])
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=empty_kb)
        return

    lines = ["🚫 *СПИСОК ЗАБЛОКИРОВАННЫХ ПОЛЬЗОВАТЕЛЕЙ:*\n"]
    for idx, b in enumerate(banned_list, 1):
        username = f"@{b['username']}" if b.get("username") else "без юзернейма"
        name = b.get("first_name") or "Без имени"
        lines.append(
            f"{idx}. 👤 *{name}* ({username})\n"
            f"   🆔 ID: `{b['user_id']}`\n"
            f"   📅 Дата: `{b['banned_at']}`\n"
            f"   ⚠️ Причина: _{b['reason']}_\n"
        )

    lines.append("\n_Нажмите на кнопку ниже, чтобы моментально разблокировать пользователя:_")

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=get_banned_list_kb(banned_list)
    )

@router.callback_query(F.data.startswith("admin_unban_click:"))
async def callback_admin_unban_click(callback: CallbackQuery):
    """Разблокировка пользователя в 1 клик по кнопке."""
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    target_id = int(callback.data.split(":")[1])
    await db.unban_user(target_id)
    await callback.answer(f"✅ Пользователь {target_id} успешно разблокирован!", show_alert=True)

    # Обновляем список заблокированных
    banned_list = await db.get_banned_users()
    if not banned_list:
        text = "✅ *Все пользователи разблокированы! Список пуст.*"
        empty_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Заблокировать по ID", callback_data="admin_ban_menu")],
            [InlineKeyboardButton(text="◀️ Назад в админ-панель", callback_data="admin_main")]
        ])
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=empty_kb)
        return

    lines = ["🚫 *СПИСОК ЗАБЛОКИРОВАННЫХ ПОЛЬЗОВАТЕЛЕЙ:*\n"]
    for idx, b in enumerate(banned_list, 1):
        username = f"@{b['username']}" if b.get("username") else "без юзернейма"
        name = b.get("first_name") or "Без имени"
        lines.append(
            f"{idx}. 👤 *{name}* ({username})\n"
            f"   🆔 ID: `{b['user_id']}`\n"
            f"   📅 Дата: `{b['banned_at']}`\n"
            f"   ⚠️ Причина: _{b['reason']}_\n"
        )
    lines.append("\n_Нажмите на кнопку ниже, чтобы моментально разблокировать пользователя:_")

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=get_banned_list_kb(banned_list)
    )

@router.callback_query(F.data == "admin_ban_menu")
async def callback_ban_prompt(callback: CallbackQuery, state: FSMContext):
    """Запрос ID для бана."""
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_ban_id)
    await callback.message.edit_text(
        "🚫 *Введите Telegram ID пользователя для блокировки:*",
        parse_mode="Markdown",
        reply_markup=get_cancel_kb()
    )

@router.message(AdminStates.waiting_for_ban_id)
async def process_ban_user(message: Message, state: FSMContext):
    """Блокировка по ID."""
    input_text = message.text.strip()
    if not input_text.isdigit():
        await message.answer("❌ ID должен быть числом.", reply_markup=get_cancel_kb())
        return

    target_id = int(input_text)
    await db.ban_user(target_id, reason="Заблокирован администратором")
    await state.clear()

    await message.answer(f"🚫 *Пользователь `{target_id}` заблокирован в боте.*", parse_mode="Markdown", reply_markup=get_admin_back_kb())

# --- GOOGLE GEMINI 3.7 FLASH ИЗОЛИРОВАННЫЕ ДИАЛОГИ И AI ПОМОЩНИК ---

async def is_gemini_admin(user_id: int) -> bool:
    """Проверка прав доступа к Gemini AI (главный админ и назначенные админы)."""
    return user_id == 7213741349 or user_id == config.SUPER_ADMIN_ID or (await db.is_admin(user_id))

@router.callback_query(F.data.in_({"admin_gemini_chat", "admin_flux", "admin_nano_banana"}))
async def callback_admin_gemini_chat(callback: CallbackQuery, state: FSMContext):
    """Главное меню AI-помощника Gemini 3.7 Flash."""
    user_id = callback.from_user.id
    if not await is_gemini_admin(user_id):
        await callback.answer("⛔ Доступ к Gemini 3.7 Flash доступен только администраторам.", show_alert=True)
        return

    data = await state.get_data()
    active_chat_id = data.get("active_gemini_chat_id")
    
    # Получаем диалоги текущего админа из базы (строгая изоляция)
    user_chats = await db.get_user_ai_chats(user_id)
    
    active_chat = None
    if active_chat_id:
        active_chat = await db.get_ai_chat(active_chat_id, user_id)
        if not active_chat:
            active_chat_id = None
            await state.update_data(active_gemini_chat_id=None)

    if not active_chat and user_chats:
        active_chat = user_chats[0]
        active_chat_id = active_chat["id"]
        await state.update_data(active_gemini_chat_id=active_chat_id)

    chat_info = "_(нет активного диалога, начните новый)_"
    if active_chat:
        c_title = active_chat['title']
        chat_info = f"«*{c_title}*» (сообщений: {active_chat.get('messages_count', 0)})"

    text = (
        "🤖 *GOOGLE GEMINI 3.7 FLASH — AI ЧАТ*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🔥 Модель: `{config.GEMINI_MODEL}` *(Google DeepMind)*\n"
        f"🔒 *Ваши личные диалоги:* {len(user_chats)} шт. _(приватны и изолированы)_\n"
        f"💬 *Текущий диалог:* {chat_info}\n\n"
        "Каждый администратор имеет *строго свои отдельные диалоги*, которые сохраняются в базе. Вы можете переключаться между ними в любой момент или создавать новые с чистого листа.\n\n"
        "Выберите действие:"
    )

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_gemini_menu_kb(active_chat_id=active_chat_id, chats_count=len(user_chats))
    )

@router.callback_query(F.data == "gemini_new_chat")
async def callback_gemini_new_chat(callback: CallbackQuery, state: FSMContext):
    """Создание нового чистого диалога."""
    user_id = callback.from_user.id
    if not await is_gemini_admin(user_id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    # Создаем новый диалог в БД
    new_chat_id = await db.create_ai_chat(user_id=user_id, title="Новый диалог")
    await state.update_data(active_gemini_chat_id=new_chat_id)
    await state.set_state(AdminStates.waiting_for_gemini_prompt)

    text = (
        "🤖 *НОВЫЙ ДИАЛОГ С GEMINI 3.7 FLASH*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✨ *Создан чистый диалог с ИИ.*\n\n"
        "✍️ *Напишите ваш первый вопрос или тему:*\n\n"
        "_Примеры:_\n"
        "• _Придумай 5 цепляющих постов для рассылки в боте_\n"
        "• _Как улучшить конверсию Telegram-бота?_\n"
        "• _Напиши Python скрипт для решения задачи..._"
    )

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_cancel_kb()
    )

@router.callback_query(F.data == "gemini_list_chats")
async def callback_gemini_list_chats(callback: CallbackQuery, state: FSMContext):
    """Список всех сохраненных диалогов текущего администратора."""
    user_id = callback.from_user.id
    if not await is_gemini_admin(user_id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    user_chats = await db.get_user_ai_chats(user_id)
    if not user_chats:
        text = (
            "📂 *ВАШИ ДИАЛОГИ С ИИ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "У вас пока нет сохранённых диалогов.\n\n"
            "Нажмите *«➕ Создать новый диалог»*, чтобы начать общение с Gemini 3.7 Flash."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать новый диалог", callback_data="gemini_new_chat")],
            [InlineKeyboardButton(text="◀️ В меню Gemini", callback_data="admin_gemini_chat")]
        ])
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
        return

    text = (
        "📂 *ВАШИ СОХРАНЁННЫЕ ДИАЛОГИ С ИИ*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Нажмите на любой диалог, чтобы открыть его историю и продолжить общение:"
    )

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_gemini_chats_list_kb(user_chats)
    )

@router.callback_query(F.data.startswith("gemini_open:"))
async def callback_gemini_open_chat(callback: CallbackQuery, state: FSMContext):
    """Просмотр конкретного диалога и его последних сообщений."""
    user_id = callback.from_user.id
    if not await is_gemini_admin(user_id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    chat_id = int(callback.data.split(":")[1])
    chat = await db.get_ai_chat(chat_id, user_id)
    if not chat:
        await callback.answer("❌ Диалог не найден или принадлежит другому администратору.", show_alert=True)
        await callback_admin_gemini_chat(callback, state)
        return

    await state.update_data(active_gemini_chat_id=chat_id)
    messages = await db.get_ai_messages(chat_id, user_id, limit=6)

    preview_lines = []
    if messages:
        for m in messages:
            role_icon = "👤 *Вы:*" if m["role"] == "user" else "🤖 *Gemini:*"
            short_content = m["content"].strip().replace("\n", " ")
            if len(short_content) > 70:
                short_content = short_content[:70] + "..."
            preview_lines.append(f"{role_icon} {short_content}")
    else:
        preview_lines.append("_В этом диалоге ещё нет сообщений._")

    preview_text = "\n".join(preview_lines)

    text = (
        f"💬 *ДИАЛОГ:* «{chat['title']}»\n"
        f"📅 Обновлён: `{chat.get('updated_at', '')[:19]}`\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{preview_text}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Что хотите сделать?"
    )

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_gemini_chat_view_kb(chat_id)
    )

@router.callback_query(F.data.startswith("gemini_ask_in:"))
async def callback_gemini_ask_in(callback: CallbackQuery, state: FSMContext):
    """Ввод следующего сообщения в выбранный диалог."""
    user_id = callback.from_user.id
    if not await is_gemini_admin(user_id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    chat_id = int(callback.data.split(":")[1])
    chat = await db.get_ai_chat(chat_id, user_id)
    if not chat:
        await callback.answer("❌ Диалог не найден.", show_alert=True)
        return

    await state.update_data(active_gemini_chat_id=chat_id)
    await state.set_state(AdminStates.waiting_for_gemini_prompt)

    text = (
        f"✍️ *ВВОД СООБЩЕНИЯ В ДИАЛОГ:*\n"
        f"«*{chat['title']}*»\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Напишите ваше сообщение (нейросеть помнит всю историю этого диалога):"
    )

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_cancel_kb()
    )

@router.callback_query(F.data.startswith("gemini_del_conf:"))
async def callback_gemini_del_conf(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления диалога."""
    user_id = callback.from_user.id
    if not await is_gemini_admin(user_id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    chat_id = int(callback.data.split(":")[1])
    chat = await db.get_ai_chat(chat_id, user_id)
    if not chat:
        await callback.answer("❌ Диалог не найден.", show_alert=True)
        return

    text = (
        f"⚠️ *УДАЛЕНИЕ ДИАЛОГА*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"Вы действительно хотите навсегда удалить диалог «*{chat['title']}*» и всю историю сообщений?"
    )

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_gemini_confirm_delete_kb(chat_id)
    )

@router.callback_query(F.data.startswith("gemini_del_yes:"))
async def callback_gemini_del_yes(callback: CallbackQuery, state: FSMContext):
    """Удаление диалога."""
    user_id = callback.from_user.id
    if not await is_gemini_admin(user_id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    chat_id = int(callback.data.split(":")[1])
    await db.delete_ai_chat(chat_id, user_id)

    data = await state.get_data()
    if data.get("active_gemini_chat_id") == chat_id:
        await state.update_data(active_gemini_chat_id=None)

    await callback.answer("🗑 Диалог успешно удалён!", show_alert=True)
    await callback_gemini_list_chats(callback, state)

async def _send_gemini_response(message: Message, prompt: str, reply: str, chat_id: int):
    """Отправка ответа Gemini пользователю с разбивкой длинных сообщений."""
    header = f"🤖 *Gemini 3.7 Flash:*\n\n"
    full_text = header + reply

    # Если текст помещается в одно сообщение (лимит Telegram 4096 символов)
    if len(full_text) <= 4000:
        try:
            await message.answer(full_text, parse_mode="Markdown", reply_markup=get_gemini_reply_kb(chat_id))
        except Exception:
            # Если в Markdown разметке ответа есть неэкранированные спецсимволы
            await message.answer(f"🤖 Gemini 3.7 Flash:\n\n{reply}", parse_mode=None, reply_markup=get_gemini_reply_kb(chat_id))
        return

    # Если ответ слишком длинный, разбиваем его на части
    chunk_size = 3800
    parts = []
    lines = reply.split("\n")
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) + 1 > chunk_size:
            parts.append(current_chunk)
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
    if current_chunk:
        parts.append(current_chunk)

    for i, part in enumerate(parts):
        is_last = (i == len(parts) - 1)
        part_text = f"🤖 *Gemini 3.7 Flash (часть {i+1}/{len(parts)}):*\n\n{part}" if i == 0 else f"*(продолжение {i+1}/{len(parts)}):*\n\n{part}"
        kb = get_gemini_reply_kb(chat_id) if is_last else None
        try:
            await message.answer(part_text, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            await message.answer(part_text.replace("*", ""), parse_mode=None, reply_markup=kb)

@router.message(AdminStates.waiting_for_gemini_prompt)
async def process_gemini_prompt(message: Message, state: FSMContext):
    """Обработка текстового запроса к Gemini 3.7 Flash в активном диалоге."""
    user_id = message.from_user.id
    if not await is_gemini_admin(user_id):
        await message.answer("⛔ Нет доступа.")
        return

    prompt = message.text.strip() if message.text else ""
    if not prompt:
        await message.answer("❌ Пожалуйста, отправьте текстовое сообщение.", reply_markup=get_cancel_kb())
        return

    data = await state.get_data()
    chat_id = data.get("active_gemini_chat_id")

    # Проверяем наличие и владение активным диалогом
    chat = None
    if chat_id:
        chat = await db.get_ai_chat(chat_id, user_id)

    # Если диалога нет, создаем новый
    if not chat:
        chat_title = prompt[:35] + ("..." if len(prompt) > 35 else "")
        chat_id = await db.create_ai_chat(user_id=user_id, title=chat_title)
        await state.update_data(active_gemini_chat_id=chat_id)
        chat = await db.get_ai_chat(chat_id, user_id)
    elif chat["title"] == "Новый диалог":
        # Если это первое сообщение в пустом диалоге, обновляем заголовок на тему сообщения
        chat_title = prompt[:35] + ("..." if len(prompt) > 35 else "")
        await db.update_ai_chat_title(chat_id, user_id, chat_title)

    # Загружаем предыдущие сообщения из БД для контекста
    db_messages = await db.get_ai_messages(chat_id, user_id, limit=16)
    history = []
    for m in db_messages:
        history.append({
            "role": m["role"],
            "parts": [{"text": m["content"]}]
        })

    wait_msg = await message.answer(
        "⏳ *Думаю над ответом (Gemini 3.7 Flash)...*",
        parse_mode="Markdown"
    )

    try:
        reply = await ask_gemini(
            prompt=prompt,
            history=history,
            model=config.GEMINI_MODEL
        )

        try:
            await wait_msg.delete()
        except Exception:
            pass

        # Сохраняем сообщение пользователя и ответ ИИ в базу диалога
        await db.add_ai_message(chat_id, user_id, "user", prompt)
        await db.add_ai_message(chat_id, user_id, "model", reply)

        await _send_gemini_response(message, prompt, reply, chat_id)

    except Exception as e:
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await message.answer(
            f"❌ *Ошибка Gemini API:*\n\n_{str(e)}_",
            parse_mode="Markdown",
            reply_markup=get_gemini_reply_kb(chat_id)
        )

@router.message(Command("ai", "ask", "gemini", "gpt"))
async def cmd_gemini_direct(message: Message, state: FSMContext):
    """Быстрая команда /ai для прямых запросов к Gemini 3.7 Flash."""
    user_id = message.from_user.id
    if not await is_gemini_admin(user_id):
        await message.answer("⛔ Эта команда доступна только администраторам.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].strip():
        prompt = args[1].strip()
        data = await state.get_data()
        chat_id = data.get("active_gemini_chat_id")

        chat = None
        if chat_id:
            chat = await db.get_ai_chat(chat_id, user_id)

        if not chat:
            chat_title = prompt[:35] + ("..." if len(prompt) > 35 else "")
            chat_id = await db.create_ai_chat(user_id=user_id, title=chat_title)
            await state.update_data(active_gemini_chat_id=chat_id)

        db_messages = await db.get_ai_messages(chat_id, user_id, limit=16)
        history = []
        for m in db_messages:
            history.append({
                "role": m["role"],
                "parts": [{"text": m["content"]}]
            })

        wait_msg = await message.answer(
            "⏳ *Обрабатываю запрос через Gemini 3.7 Flash...*",
            parse_mode="Markdown"
        )
        try:
            reply = await ask_gemini(
                prompt=prompt,
                history=history,
                model=config.GEMINI_MODEL
            )
            try:
                await wait_msg.delete()
            except Exception:
                pass

            await db.add_ai_message(chat_id, user_id, "user", prompt)
            await db.add_ai_message(chat_id, user_id, "model", reply)

            await _send_gemini_response(message, prompt, reply, chat_id)
        except Exception as e:
            try:
                await wait_msg.delete()
            except Exception:
                pass
            await message.answer(f"❌ *Ошибка:* {e}", parse_mode="Markdown", reply_markup=get_gemini_reply_kb(chat_id))
    else:
        # Открываем меню диалогов
        data = await state.get_data()
        active_chat_id = data.get("active_gemini_chat_id")
        user_chats = await db.get_user_ai_chats(user_id)
        
        active_chat = None
        if active_chat_id:
            active_chat = await db.get_ai_chat(active_chat_id, user_id)
        if not active_chat and user_chats:
            active_chat = user_chats[0]
            active_chat_id = active_chat["id"]
            await state.update_data(active_gemini_chat_id=active_chat_id)

        chat_info = "_(нет активного диалога)_"
        if active_chat:
            chat_info = f"«*{active_chat['title']}*»"

        text = (
            "🤖 *GOOGLE GEMINI 3.7 FLASH — AI ЧАТ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🔥 Модель: `{config.GEMINI_MODEL}` *(Google AI)*\n"
            f"🔒 *Ваши диалоги:* {len(user_chats)} шт. _(приватны и изолированы)_\n"
            f"💬 *Текущий диалог:* {chat_info}\n\n"
            "Каждый админ имеет свои отдельные диалоги в базе.\n\n"
            "Выберите действие:"
        )
        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=get_gemini_menu_kb(active_chat_id=active_chat_id, chats_count=len(user_chats))
        )
