from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Главная нижняя клавиатура бота."""
    keyboard = [
        [
            KeyboardButton(text="🔗 Моя ссылка"),
            KeyboardButton(text="ℹ️ О боте / Инструкция")
        ]
    ]
    
    if is_admin:
        keyboard.append([KeyboardButton(text="⚡ Админ-панель")])
        
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
