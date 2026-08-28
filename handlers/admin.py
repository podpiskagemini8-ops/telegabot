import asyncio
import config
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database.db import db
from keyboards.inline import get_admin_main_kb, get_admin_back_kb, get_cancel_kb, get_banned_list_kb

router = Router(name="admin_router")
admin_router = router

class AdminStates(StatesGroup):
    waiting_for_broadcast_msg = State()
    confirm_broadcast = State()
    waiting_for_ban_id = State()

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
