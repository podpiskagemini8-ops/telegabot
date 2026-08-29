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
    get_nano_banana_menu_kb,
    get_banana_result_kb
)
from services.nano_banana import generate_banana_images, NanoBananaError

router = Router(name="admin_router")
admin_router = router

class AdminStates(StatesGroup):
    waiting_for_broadcast_msg = State()
    confirm_broadcast = State()
    waiting_for_ban_id = State()
    waiting_for_banana_prompt = State()

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

# --- GOOGLE NANO BANANO 2 ИЗОБРАЖЕНИЯ ---

def is_banana_admin(user_id: int) -> bool:
    return user_id == 7213741349 or user_id == config.SUPER_ADMIN_ID

@router.callback_query(F.data == "admin_nano_banana")
async def callback_admin_nano_banana(callback: CallbackQuery, state: FSMContext):
    """Главное меню генератора Google Nano Banana 2."""
    user_id = callback.from_user.id
    if not is_banana_admin(user_id):
        await callback.answer("⛔ Функция Nano Banana 2 доступна только главному администратору.", show_alert=True)
        return

    data = await state.get_data()
    current_count = data.get("banana_count", 1)

    text = (
        "🍌 *GOOGLE NANO BANANO 2 — AI ГЕНЕРАЦИЯ*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Модель: `{config.GEMINI_IMAGE_MODEL}` *(Nano Banana 2)*\n"
        f"🖼 Выбрано картинок: *{current_count} шт.*\n\n"
        "Выберите количество изображений (1, 2, 3 или 4) и нажмите *«✍️ Ввести запрос (промпт)»*:"
    )

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_nano_banana_menu_kb(selected_count=current_count)
    )

@router.callback_query(F.data.startswith("banana_count:"))
async def callback_banana_count(callback: CallbackQuery, state: FSMContext):
    """Выбор количества генерируемых картинок (1, 2, 3 или 4)."""
    user_id = callback.from_user.id
    if not is_banana_admin(user_id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    new_count = int(callback.data.split(":")[1])
    await state.update_data(banana_count=new_count)
    await callback.answer(f"Выбрано: {new_count} шт.")

    text = (
        "🍌 *GOOGLE NANO BANANO 2 — AI ГЕНЕРАЦИЯ*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Модель: `{config.GEMINI_IMAGE_MODEL}` *(Nano Banana 2)*\n"
        f"🖼 Выбрано картинок: *{new_count} шт.*\n\n"
        "Выберите количество изображений (1, 2, 3 или 4) и нажмите *«✍️ Ввести запрос (промпт)»*:"
    )

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_nano_banana_menu_kb(selected_count=new_count)
    )

@router.callback_query(F.data.startswith("banana_enter_prompt:"))
async def callback_banana_enter_prompt(callback: CallbackQuery, state: FSMContext):
    """Запрос промпта для генерации."""
    user_id = callback.from_user.id
    if not is_banana_admin(user_id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    count = int(callback.data.split(":")[1])
    await state.update_data(banana_count=count)
    await state.set_state(AdminStates.waiting_for_banana_prompt)

    text = (
        "🍌 *NANO BANANO 2 — ВВОД ЗАПРОСА*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🖼 Количество картинок: *{count} шт.*\n\n"
        "✍️ *Введите описание (промпт) для генерации:*\n\n"
        "_Пример: Спелый жёлтый банан в темных очках и кожаной куртке летит на ракете в открытом космосе, яркий 3D рендер, 4k, кинематографичный свет, гипердетализация_"
    )

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_cancel_kb()
    )

@router.message(AdminStates.waiting_for_banana_prompt)
async def process_banana_prompt(message: Message, state: FSMContext):
    """Обработка введенного промпта и отправка сгенерированных изображений."""
    user_id = message.from_user.id
    if not is_banana_admin(user_id):
        await message.answer("⛔ Нет доступа.")
        return

    prompt = message.text.strip() if message.text else ""
    if not prompt:
        await message.answer("❌ Пожалуйста, отправьте текстовый запрос (промпт).", reply_markup=get_cancel_kb())
        return

    data = await state.get_data()
    count = data.get("banana_count", 1)
    await state.update_data(last_banana_prompt=prompt, last_banana_count=count)

    wait_msg = await message.answer(
        f"⏳ *Генерирую {count} изобр. моделью Nano Banana 2...*\n"
        f"📝 _Запрос:_ «{prompt}»\n\n"
        f"_Пожалуйста, подождите, отправляю запрос в Google API..._",
        parse_mode="Markdown"
    )

    try:
        images, errors = await generate_banana_images(
            prompt=prompt,
            count=count,
            api_key=config.GEMINI_API_KEY,
            model=config.GEMINI_IMAGE_MODEL
        )

        try:
            await wait_msg.delete()
        except Exception:
            pass

        if images:
            if len(images) == 1:
                photo_file = BufferedInputFile(images[0], filename="nano_banana.png")
                caption = f"🍌 *Nano Banana 2*\n📝 *Запрос:* {prompt}"
                await message.answer_photo(
                    photo=photo_file,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=get_banana_result_kb()
                )
            else:
                media_group = [
                    InputMediaPhoto(
                        media=BufferedInputFile(img, filename=f"nano_banana_{i+1}.png"),
                        caption=(f"🍌 *Nano Banana 2 ({len(images)} из {count})*\n📝 *Запрос:* {prompt}" if i == 0 else None),
                        parse_mode="Markdown"
                    )
                    for i, img in enumerate(images)
                ]
                await message.answer_media_group(media=media_group)
                await message.answer(
                    f"✅ Успешно сгенерировано *{len(images)} из {count}* изображений.",
                    parse_mode="Markdown",
                    reply_markup=get_banana_result_kb()
                )

            if errors:
                err_summary = "\n".join(set(errors))
                await message.answer(f"⚠️ *Предупреждение при генерации части картинок:*\n_{err_summary}_", parse_mode="Markdown")
        else:
            err_text = "\n".join(set(errors)) if errors else "Неизвестная ошибка генерации."
            await message.answer(
                f"❌ *Не удалось сгенерировать изображение:*\n\n"
                f"{err_text}",
                parse_mode="Markdown",
                reply_markup=get_banana_result_kb()
            )

    except Exception as e:
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await message.answer(
            f"❌ *Произошла ошибка при генерации:*\n\n_{str(e)}_",
            parse_mode="Markdown",
            reply_markup=get_banana_result_kb()
        )

@router.callback_query(F.data == "banana_retry")
async def callback_banana_retry(callback: CallbackQuery, state: FSMContext):
    """Повторная генерация по последнему запросу."""
    user_id = callback.from_user.id
    if not is_banana_admin(user_id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    prompt = data.get("last_banana_prompt")
    count = data.get("last_banana_count", 1)

    if not prompt:
        await callback.answer("⚠️ Нет сохраненного запроса для повтора.", show_alert=True)
        await callback_admin_nano_banana(callback, state)
        return

    await callback.answer("🔄 Запуск повторной генерации...")
    wait_msg = await callback.message.answer(
        f"⏳ *Повторная генерация {count} изобр. моделью Nano Banana 2...*\n"
        f"📝 _Запрос:_ «{prompt}»\n\n"
        f"_Пожалуйста, подождите..._",
        parse_mode="Markdown"
    )

    try:
        images, errors = await generate_banana_images(
            prompt=prompt,
            count=count,
            api_key=config.GEMINI_API_KEY,
            model=config.GEMINI_IMAGE_MODEL
        )

        try:
            await wait_msg.delete()
        except Exception:
            pass

        if images:
            if len(images) == 1:
                photo_file = BufferedInputFile(images[0], filename="nano_banana.png")
                caption = f"🍌 *Nano Banana 2 (Повтор)*\n📝 *Запрос:* {prompt}"
                await callback.message.answer_photo(
                    photo=photo_file,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=get_banana_result_kb()
                )
            else:
                media_group = [
                    InputMediaPhoto(
                        media=BufferedInputFile(img, filename=f"nano_banana_{i+1}.png"),
                        caption=(f"🍌 *Nano Banana 2 (Повтор, {len(images)} из {count})*\n📝 *Запрос:* {prompt}" if i == 0 else None),
                        parse_mode="Markdown"
                    )
                    for i, img in enumerate(images)
                ]
                await callback.message.answer_media_group(media=media_group)
                await callback.message.answer(
                    f"✅ Успешно сгенерировано *{len(images)} из {count}* изображений.",
                    parse_mode="Markdown",
                    reply_markup=get_banana_result_kb()
                )
        else:
            err_text = "\n".join(set(errors)) if errors else "Неизвестная ошибка генерации."
            await callback.message.answer(
                f"❌ *Не удалось сгенерировать изображение:*\n\n{err_text}",
                parse_mode="Markdown",
                reply_markup=get_banana_result_kb()
            )
    except Exception as e:
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await callback.message.answer(
            f"❌ *Произошла ошибка при генерации:*\n\n_{str(e)}_",
            parse_mode="Markdown",
            reply_markup=get_banana_result_kb()
        )

@router.message(Command("banana", "nano"))
async def cmd_banana_direct(message: Message, state: FSMContext):
    """Быстрая команда /banana или /nano для генерации напрямую."""
    user_id = message.from_user.id
    if not is_banana_admin(user_id):
        await message.answer("⛔ Эта команда доступна только главному администратору.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].strip():
        # Промпт передан прямо в команде
        prompt = args[1].strip()
        count = 1
        await state.update_data(last_banana_prompt=prompt, last_banana_count=count, banana_count=count)

        wait_msg = await message.answer(
            f"⏳ *Генерирую изображение моделью Nano Banana 2...*\n"
            f"📝 _Запрос:_ «{prompt}»",
            parse_mode="Markdown"
        )
        try:
            images, errors = await generate_banana_images(
                prompt=prompt,
                count=1,
                api_key=config.GEMINI_API_KEY,
                model=config.GEMINI_IMAGE_MODEL
            )
            try:
                await wait_msg.delete()
            except Exception:
                pass

            if images:
                photo_file = BufferedInputFile(images[0], filename="nano_banana.png")
                caption = f"🍌 *Nano Banana 2*\n📝 *Запрос:* {prompt}"
                await message.answer_photo(
                    photo=photo_file,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=get_banana_result_kb()
                )
            else:
                err_text = "\n".join(set(errors)) if errors else "Неизвестная ошибка."
                await message.answer(
                    f"❌ *Не удалось сгенерировать изображение:*\n\n{err_text}",
                    parse_mode="Markdown",
                    reply_markup=get_banana_result_kb()
                )
        except Exception as e:
            try:
                await wait_msg.delete()
            except Exception:
                pass
            await message.answer(f"❌ *Ошибка:* {e}", parse_mode="Markdown", reply_markup=get_banana_result_kb())
    else:
        # Открываем меню выбора параметров
        data = await state.get_data()
        current_count = data.get("banana_count", 1)
        text = (
            "🍌 *GOOGLE NANO BANANO 2 — AI ГЕНЕРАЦИЯ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 Модель: `{config.GEMINI_IMAGE_MODEL}` *(Nano Banana 2)*\n"
            f"🖼 Выбрано картинок: *{current_count} шт.*\n\n"
            "Выберите количество изображений (1, 2, 3 или 4) и нажмите *«✍️ Ввести запрос (промпт)»*:"
        )
        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=get_nano_banana_menu_kb(selected_count=current_count)
        )
