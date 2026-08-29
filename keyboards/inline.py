from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from urllib.parse import quote

def get_personal_link_kb(bot_username: str, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура под сообщением со ссылкой пользователя."""
    link = f"https://t.me/{bot_username}?start={user_id}"
    share_text = "Напиши мне анонимное сообщение! 🤫👇"
    share_url = f"https://t.me/share/url?url={quote(link)}&text={quote(share_text)}"
    
    keyboard = [
        [
            InlineKeyboardButton(text="📲 Поделиться ссылкой", url=share_url)
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_anon_message_kb(message_id: int, is_admin: bool = False) -> InlineKeyboardMarkup:
    """
    Клавиатура под полученным анонимным сообщением:
    - Кнопка 'Ответить' для всех пользователей
    - Секретная кнопка 'Узнать кто это' ТОЛЬКО для администраторов
    """
    keyboard = [
        [
            InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply:{message_id}")
        ]
    ]
    
    # Если получатель - администратор из конфига/БД, добавляем кнопку деанонимизации
    if is_admin:
        keyboard.append([
            InlineKeyboardButton(text="🕵️‍♂️ Узнать кто это", callback_data=f"reveal:{message_id}")
        ])
        
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_cancel_kb() -> InlineKeyboardMarkup:
    """Кнопка отмены текущего действия."""
    keyboard = [
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_main_kb(is_super_admin: bool = False) -> InlineKeyboardMarkup:
    """Главное меню админ-панели."""
    keyboard = [
        [
            InlineKeyboardButton(text="🤖 Чат с Gemini 3.7 Flash", callback_data="admin_gemini_chat")
        ],
        [
            InlineKeyboardButton(text="📜 Последние сообщения", callback_data="admin_recent_msgs")
        ],
        [
            InlineKeyboardButton(text="🚫 Заблокированные пользователи", callback_data="admin_banned_list")
        ]
    ]
    if is_super_admin:
        keyboard.insert(1, [
            InlineKeyboardButton(text="🌸 Гемини Маши", callback_data="admin_masha_gemini")
        ])
        keyboard.insert(3, [
            InlineKeyboardButton(text="📢 Рассылка всем", callback_data="admin_broadcast")
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_gemini_menu_kb(active_chat_id: Optional[int] = None, chats_count: int = 0) -> InlineKeyboardMarkup:
    """Главное меню AI-помощника Gemini 3.7 Flash."""
    keyboard = []
    if active_chat_id:
        keyboard.append([
            InlineKeyboardButton(text="✍️ Продолжить текущий диалог", callback_data=f"gemini_ask_in:{active_chat_id}")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text="✍️ Начать диалог с ИИ", callback_data="gemini_new_chat")
        ])

    keyboard.append([
        InlineKeyboardButton(text="➕ Новый диалог с чистого листа", callback_data="gemini_new_chat")
    ])

    if chats_count > 0:
        keyboard.append([
            InlineKeyboardButton(text=f"📂 Мои сохранённые диалоги ({chats_count})", callback_data="gemini_list_chats")
        ])

    keyboard.append([
        InlineKeyboardButton(text="◀️ В админ-панель", callback_data="admin_main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_gemini_chats_list_kb(chats: List[dict]) -> InlineKeyboardMarkup:
    """Список сохраненных диалогов администратора."""
    keyboard = []
    for c in chats[:15]:
        chat_id = c["id"]
        title = c["title"]
        if len(title) > 28:
            title = title[:28] + "..."
        msg_count = c.get("messages_count", 0)
        keyboard.append([
            InlineKeyboardButton(
                text=f"💬 {title} ({msg_count})",
                callback_data=f"gemini_open:{chat_id}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(text="➕ Создать новый диалог", callback_data="gemini_new_chat")
    ])
    keyboard.append([
        InlineKeyboardButton(text="◀️ Назад в меню Gemini", callback_data="admin_gemini_chat")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_gemini_chat_view_kb(chat_id: int) -> InlineKeyboardMarkup:
    """Меню открытого диалога."""
    keyboard = [
        [
            InlineKeyboardButton(text="✍️ Написать в этот диалог", callback_data=f"gemini_ask_in:{chat_id}")
        ],
        [
            InlineKeyboardButton(text="🗑 Удалить диалог", callback_data=f"gemini_del_conf:{chat_id}"),
            InlineKeyboardButton(text="📂 Все диалоги", callback_data="gemini_list_chats")
        ],
        [
            InlineKeyboardButton(text="◀️ В меню Gemini", callback_data="admin_gemini_chat")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_gemini_reply_kb(chat_id: int) -> InlineKeyboardMarkup:
    """Кнопки под ответом Gemini в конкретном диалоге."""
    keyboard = [
        [
            InlineKeyboardButton(text="✍️ Ответить дальше", callback_data=f"gemini_ask_in:{chat_id}"),
            InlineKeyboardButton(text="➕ Новый диалог", callback_data="gemini_new_chat")
        ],
        [
            InlineKeyboardButton(text="📂 Мои диалоги", callback_data="gemini_list_chats"),
            InlineKeyboardButton(text="◀️ В админ-панель", callback_data="admin_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_gemini_confirm_delete_kb(chat_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления диалога."""
    keyboard = [
        [
            InlineKeyboardButton(text="🗑 Да, удалить диалог", callback_data=f"gemini_del_yes:{chat_id}"),
            InlineKeyboardButton(text="◀️ Отмена", callback_data=f"gemini_open:{chat_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_masha_chats_list_kb(chats: List[dict]) -> InlineKeyboardMarkup:
    """Список диалогов Маши с Gemini для главного админа."""
    keyboard = []
    for c in chats[:15]:
        chat_id = c["id"]
        title = c["title"]
        if len(title) > 28:
            title = title[:28] + "..."
        msg_count = c.get("messages_count", 0)
        keyboard.append([
            InlineKeyboardButton(
                text=f"💬 {title} ({msg_count})",
                callback_data=f"masha_chat_view:{chat_id}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(text="🔄 Обновить список", callback_data="admin_masha_gemini")
    ])
    keyboard.append([
        InlineKeyboardButton(text="◀️ Назад в админ-панель", callback_data="admin_main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_masha_chat_view_kb(chat_id: int) -> InlineKeyboardMarkup:
    """Кнопки при просмотре диалога Маши."""
    keyboard = [
        [
            InlineKeyboardButton(text="🔄 Обновить переписку", callback_data=f"masha_chat_view:{chat_id}"),
            InlineKeyboardButton(text="📂 Все диалоги Маши", callback_data="admin_masha_gemini")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад в админ-панель", callback_data="admin_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_back_kb() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню админки."""
    keyboard = [
        [
            InlineKeyboardButton(text="◀️ Назад в админ-панель", callback_data="admin_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_banned_list_kb(banned_users: list) -> InlineKeyboardMarkup:
    """Клавиатура списка заблокированных с кнопками быстрой разблокировки."""
    keyboard = []
    # Для каждого заблокированного пользователя добавляем кнопку быстрой разблокировки в 1 клик
    for b in banned_users[:8]:
        u_id = b["user_id"]
        name = b.get("first_name") or f"ID {u_id}"
        keyboard.append([
            InlineKeyboardButton(text=f"🟢 Разблокировать: {name} ({u_id})", callback_data=f"admin_unban_click:{u_id}")
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="➕ Заблокировать по ID", callback_data="admin_ban_menu")
    ])
    keyboard.append([
        InlineKeyboardButton(text="◀️ Назад в админ-панель", callback_data="admin_main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_reveal_details_kb(sender_id: int, username: str | None = None) -> InlineKeyboardMarkup:
    """Кнопки под карточкой данных об отправителе."""
    keyboard = []
    if username:
        clean_user = username.replace("@", "")
        keyboard.append([
            InlineKeyboardButton(text=f"👤 Профиль @{clean_user}", url=f"https://t.me/{clean_user}")
        ])
    keyboard.append([
        InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"quick_ban:{sender_id}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
