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
            InlineKeyboardButton(text="📜 Последние сообщения", callback_data="admin_recent_msgs")
        ],
        [
            InlineKeyboardButton(text="🚫 Заблокированные пользователи", callback_data="admin_banned_list")
        ]
    ]
    if is_super_admin:
        keyboard.insert(0, [
            InlineKeyboardButton(text="🤖 Чат с Gemini 3.7 Flash", callback_data="admin_gemini_chat")
        ])
        keyboard.insert(2, [
            InlineKeyboardButton(text="📢 Рассылка всем", callback_data="admin_broadcast")
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_gemini_menu_kb() -> InlineKeyboardMarkup:
    """Меню чата с Gemini 3.7 Flash."""
    keyboard = [
        [
            InlineKeyboardButton(text="✍️ Задать вопрос / Написать запрос", callback_data="gemini_ask")
        ],
        [
            InlineKeyboardButton(text="🧹 Очистить контекст", callback_data="gemini_clear"),
            InlineKeyboardButton(text="◀️ В админ-панель", callback_data="admin_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_gemini_reply_kb() -> InlineKeyboardMarkup:
    """Кнопки под ответом Gemini."""
    keyboard = [
        [
            InlineKeyboardButton(text="✍️ Продолжить диалог", callback_data="gemini_ask"),
            InlineKeyboardButton(text="🧹 Очистить диалог", callback_data="gemini_clear")
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
