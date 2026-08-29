import os
from typing import List
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

# Список ID администраторов по умолчанию (предустановлены ваши ID)
ADMIN_IDS: List[int] = [7213741349, 2083953144, 8295558531]
raw_admins = os.getenv("ADMIN_IDS", "").strip()

if raw_admins:
    parsed_admins = []
    for item in raw_admins.split(","):
        item = item.strip()
        if item.isdigit():
            parsed_admins.append(int(item))
    if parsed_admins:
        ADMIN_IDS = parsed_admins

# Путь к файлу базы данных SQLite
DB_PATH: str = os.getenv("DB_PATH", "database.sqlite3")

# Супер-администратор (владелец)
SUPER_ADMIN_ID: int = 7213741349

# Прокси (если используется)
PROXY_URL: str = os.getenv("PROXY_URL", "").strip() or os.getenv("HTTPS_PROXY", "").strip() or os.getenv("HTTP_PROXY", "").strip()

import base64

# Предустановленный ключ Google Gemini / Nano Banana 2
_DEFAULT_GEMINI_KEY = base64.b64decode("QVEuQWI4Uk42SXlEbmJ0VmtGZVBjM2dmOWctOWluX1ZLUFZQaXpZcWkwM1ZVaE5OTmF2OWc=").decode("utf-8")

# API ключ Google Gemini / Nano Banana
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip() or _DEFAULT_GEMINI_KEY
GEMINI_IMAGE_MODEL: str = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image").strip()
