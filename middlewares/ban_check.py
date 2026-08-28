from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from database.db import db

class BanCheckMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id:
            # Обновляем профиль пользователя при любой активности
            from_user = event.from_user
            await db.upsert_user(
                user_id=from_user.id,
                username=from_user.username,
                first_name=from_user.first_name,
                last_name=from_user.last_name
            )

            # Проверяем, заблокирован ли пользователь
            if await db.is_banned(user_id):
                if isinstance(event, Message):
                    await event.answer("🚫 *Вы заблокированы в этом боте за нарушение правил.*", parse_mode="Markdown")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 Вы заблокированы в этом боте.", show_alert=True)
                return

        return await handler(event, data)
