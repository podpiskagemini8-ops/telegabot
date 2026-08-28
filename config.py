import os
from typing import List
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

# Список ID администраторов по умолчанию из .env
raw_admins = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS: List[int] = []

if raw_admins:
    for item in raw_admins.split(","):
        item = item.strip()
        if item.isdigit():
            ADMIN_IDS.append(int(item))

# Путь к файлу базы данных SQLite
DB_PATH: str = os.getenv("DB_PATH", "database.sqlite3")

# Супер-администратор (владелец)
SUPER_ADMIN_ID: int = 7213741349

# Прокси (если используется)
PROXY_URL: str = os.getenv("PROXY_URL", "").strip() or os.getenv("HTTPS_PROXY", "").strip() or os.getenv("HTTP_PROXY", "").strip()
