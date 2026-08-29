import asyncio
import base64
import json
import logging
from typing import List, Optional, Tuple
import aiohttp
import config

logger = logging.getLogger(__name__)

BASE_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models"

class NanoBananaError(Exception):
    """Кастомное исключение для ошибок генерации Nano Banana."""
    pass

async def generate_banana_image(
    prompt: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    proxy: Optional[str] = None
) -> bytes:
    """
    Генерация одного изображения с использованием модели Google Nano Banana (gemini-3.1-flash-image).
    
    :param prompt: Текстовое описание желаемого изображения.
    :param api_key: Ключ Google Gemini API.
    :param model: Имя модели (по умолчанию gemini-3.1-flash-image).
    :param proxy: Прокси-сервер при необходимости.
    :return: Бинарные данные изображения (bytes).
    """
    key = api_key or config.GEMINI_API_KEY
    if not key:
        raise NanoBananaError("API ключ Google Gemini не указан.")

    target_model = model or getattr(config, "GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
    url = f"{BASE_GEMINI_URL}/{target_model}:generateContent?key={key}"
    proxy_url = proxy or getattr(config, "PROXY_URL", None) or None

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"]
        }
    }

    timeout = aiohttp.ClientTimeout(total=90)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                proxy=proxy_url
            ) as response:
                status = response.status
                response_text = await response.text()

                if status != 200:
                    try:
                        err_data = json.loads(response_text)
                        err_msg = err_data.get("error", {}).get("message", response_text)
                        err_status = err_data.get("error", {}).get("status", "")
                    except Exception:
                        err_msg = response_text
                        err_status = ""

                    if status == 429:
                        raise NanoBananaError(
                            "⚠️ Превышен лимит запросов / квота Google API (429 Resource Exhausted).\n"
                            "Для модели Nano Banana 2 (gemini-3.1-flash-image) требуется проект Google Cloud с включенным биллингом (Pay-as-you-go)."
                        )
                    elif status == 400:
                        raise NanoBananaError(
                            f"❌ Ошибка запроса (400 Bad Request): {err_msg}"
                        )
                    elif status in (401, 403):
                        raise NanoBananaError(
                            f"⛔ Ошибка авторизации ({status}): Проверьте правильность API ключа."
                        )
                    else:
                        raise NanoBananaError(
                            f"❌ Ошибка API Google ({status}): {err_msg}"
                        )

                data = json.loads(response_text)
                candidates = data.get("candidates", [])
                if not candidates:
                    raise NanoBananaError("Google API не вернул кандидатов (возможно, сработал фильтр безопасности).")

                # Извлекаем изображение из частей контента
                for candidate in candidates:
                    parts = candidate.get("content", {}).get("parts", [])
                    for part in parts:
                        inline_data = part.get("inlineData") or part.get("inline_data")
                        if inline_data and "data" in inline_data:
                            b64_data = inline_data["data"]
                            return base64.b64decode(b64_data)

                # Если изображение не найдено, проверяем текст ответа
                text_response = ""
                for candidate in candidates:
                    for part in candidate.get("content", {}).get("parts", []):
                        if "text" in part:
                            text_response += part["text"] + "\n"

                if text_response:
                    raise NanoBananaError(f"Модель вернула только текст без изображения:\n{text_response.strip()}")

                raise NanoBananaError("Изображение не найдено в ответе модели.")

        except asyncio.TimeoutError:
            raise NanoBananaError("⏱️ Превышено время ожидания ответа от Google API (Timeout).")
        except aiohttp.ClientError as e:
            raise NanoBananaError(f"🌐 Ошибка сети при обращении к Google API: {e}")

async def generate_banana_images(
    prompt: str,
    count: int = 1,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    proxy: Optional[str] = None
) -> Tuple[List[bytes], List[str]]:
    """
    Генерация нескольких изображений (от 1 до 4) параллельно.
    
    :param prompt: Текстовый промпт.
    :param count: Количество изображений (1..4).
    :return: Кортеж (список байтов сгенерированных изображений, список ошибок при генерации отдельных изображений).
    """
    count = max(1, min(count, 4))
    tasks = [
        generate_banana_image(prompt=prompt, api_key=api_key, model=model, proxy=proxy)
        for _ in range(count)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    images: List[bytes] = []
    errors: List[str] = []

    for res in results:
        if isinstance(res, Exception):
            errors.append(str(res))
        elif isinstance(res, bytes):
            images.append(res)

    return images, errors
