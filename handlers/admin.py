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
    get_gemini_reply_kb
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

# --- GOOGLE GEMINI 3.7 FLASH ТЕКСТОВЫЙ ЧАТ И AI ПОМОЩНИК ---

def is_gemini_admin(user_id: int) -> bool:
    return user_id == 7213741349 or user_id == config.SUPER_ADMIN_ID

@router.callback_query(F.data.in_({"admin_gemini_chat", "admin_flux", "admin_nano_banana"}))
async def callback_admin_gemini_chat(callback: CallbackQuery, state: FSMContext):
    """Главное меню AI-помощника Gemini 3.7 Flash."""
    user_id = callback.from_user.id
    if not is_gemini_admin(user_id):
        await callback.answer("⛔ Доступ к Gemini 3.7 Flash разрешён только главному администратору.", show_alert=True)
        return

    data = await state.get_data()
    history = data.get("gemini_history", [])
    history_count = len([h for h in history if h.get("role") == "user"])

    text = (
        "🤖 *GOOGLE GEMINI 3.7 FLASH — AI ЧАТ*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🔥 Модель: `{config.GEMINI_MODEL}` *(Google AI)*\n"
        f"💬 Сообщений в памяти: *{history_count}*\n\n"
        "Вы можете задавать любые вопросы, просить составить текст рассылки, написать или проверить код, решить задачу или вести диалог.\n\n"
        "Нажмите *«✍️ Задать вопрос»* или отправьте команду `/ai <ваш запрос>`:"
    )

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_gemini_menu_kb()
    )

@router.callback_query(F.data == "gemini_ask")
async def callback_gemini_ask(callback: CallbackQuery, state: FSMContext):
    """Запрос текста вопроса/задачи для нейросети."""
    user_id = callback.from_user.id
    if not is_gemini_admin(user_id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_gemini_prompt)
    text = (
        "🤖 *GEMINI 3.7 FLASH — ВВОД ЗАПРОСА*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✍️ *Введите ваш вопрос, задачу или тему для нейросети:*\n\n"
        "_Примеры:_\n"
        "• _Придумай 5 цепляющих постов для рассылки в боте_\n"
        "• _Как настроить рекламу Telegram-канала без бюджета?_\n"
        "• _Напиши Python скрипт для парсинга..._"
    )

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_cancel_kb()
    )

@router.callback_query(F.data == "gemini_clear")
async def callback_gemini_clear(callback: CallbackQuery, state: FSMContext):
    """Очистка контекста диалога."""
    user_id = callback.from_user.id
    if not is_gemini_admin(user_id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.update_data(gemini_history=[])
    await callback.answer("🧹 История диалога с Gemini очищена!", show_alert=True)
    await callback_admin_gemini_chat(callback, state)

async def _send_gemini_response(message: Message, prompt: str, reply: str):
    """Отправка ответа Gemini пользователю с разбивкой длинных сообщений."""
    header = f"🤖 *Gemini 3.7 Flash:*\n\n"
    full_text = header + reply

    # Если текст помещается в одно сообщение (лимит Telegram 4096 символов)
    if len(full_text) <= 4000:
        try:
            await message.answer(full_text, parse_mode="Markdown", reply_markup=get_gemini_reply_kb())
        except Exception:
            # Если в Markdown разметке ответа есть неэкранированные спецсимволы
            await message.answer(f"🤖 Gemini 3.7 Flash:\n\n{reply}", parse_mode=None, reply_markup=get_gemini_reply_kb())
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
        kb = get_gemini_reply_kb() if is_last else None
        try:
            await message.answer(part_text, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            await message.answer(part_text.replace("*", ""), parse_mode=None, reply_markup=kb)

@router.message(AdminStates.waiting_for_gemini_prompt)
async def process_gemini_prompt(message: Message, state: FSMContext):
    """Обработка текстового запроса к Gemini 3.7 Flash."""
    user_id = message.from_user.id
    if not is_gemini_admin(user_id):
        await message.answer("⛔ Нет доступа.")
        return

    prompt = message.text.strip() if message.text else ""
    if not prompt:
        await message.answer("❌ Пожалуйста, отправьте текстовый запрос.", reply_markup=get_cancel_kb())
        return

    data = await state.get_data()
    history = data.get("gemini_history", [])

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

        # Добавляем в историю (ограничиваем последними 12 репликами)
        history.append({"role": "user", "parts": [{"text": prompt}]})
        history.append({"role": "model", "parts": [{"text": reply}]})
        if len(history) > 12:
            history = history[-12:]
        await state.update_data(gemini_history=history)

        await _send_gemini_response(message, prompt, reply)

    except Exception as e:
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await message.answer(
            f"❌ *Ошибка Gemini API:*\n\n_{str(e)}_",
            parse_mode="Markdown",
            reply_markup=get_gemini_reply_kb()
        )

@router.message(Command("ai", "ask", "gemini", "gpt"))
async def cmd_gemini_direct(message: Message, state: FSMContext):
    """Быстрая команда /ai для прямых запросов к Gemini 3.7 Flash."""
    user_id = message.from_user.id
    if not is_gemini_admin(user_id):
        await message.answer("⛔ Эта команда доступна только главному администратору.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].strip():
        prompt = args[1].strip()
        data = await state.get_data()
        history = data.get("gemini_history", [])

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

            history.append({"role": "user", "parts": [{"text": prompt}]})
            history.append({"role": "model", "parts": [{"text": reply}]})
            if len(history) > 12:
                history = history[-12:]
            await state.update_data(gemini_history=history)

            await _send_gemini_response(message, prompt, reply)
        except Exception as e:
            try:
                await wait_msg.delete()
            except Exception:
                pass
            await message.answer(f"❌ *Ошибка:* {e}", parse_mode="Markdown", reply_markup=get_gemini_reply_kb())
    else:
        await callback_admin_gemini_chat(message, state)
