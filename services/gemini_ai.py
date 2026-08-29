import asyncio
import json
import logging
from typing import List, Optional, Dict, Any
import aiohttp
import config

logger = logging.getLogger(__name__)

BASE_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models"

class GeminiError(Exception):
    """Исключение для ошибок вызова Google Gemini API."""
    pass

async def ask_gemini(
    prompt: str,
    history: Optional[List[Dict[str, Any]]] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    system_instruction: Optional[str] = None
) -> str:
    """
    Отправка текстового запроса или ведение диалога с Google Gemini (gemini-3.7-flash / gemini-3.5-flash).
    Автоматически делает повторные попытки при временной нагрузке и переключается между быстрыми моделями.
    
    :param prompt: Текстовый запрос пользователя.
    :param history: Предыдущая история диалога.
    :param api_key: Ключ API.
    :param model: Имя модели.
    :param system_instruction: Системная инструкция для модели.
    :return: Текстовый ответ модели.
    """
    key = api_key or getattr(config, "GEMINI_API_KEY", "") or getattr(config, "_DEFAULT_GEMINI_KEY", "")
    if not key:
        raise GeminiError("API ключ Google Gemini не указан.")

    preferred_model = model or getattr(config, "GEMINI_MODEL", "gemini-3.7-flash")
    
    # Список самых стабильных и быстрых моделей в порядке приоритета
    models_to_try = [preferred_model]
    for fallback_m in ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-flash-lite-latest", "gemini-3.6-flash"]:
        if fallback_m not in models_to_try:
            models_to_try.append(fallback_m)

    proxy_url = getattr(config, "PROXY_URL", None) or None

    contents: List[Dict[str, Any]] = []
    if history:
        contents.extend(history)

    contents.append({
        "role": "user",
        "parts": [{"text": prompt.strip()}]
    })

    payload: Dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": 8192
        }
    }

    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    timeout = aiohttp.ClientTimeout(total=45, connect=10)
    last_error_msg = None

    async with aiohttp.ClientSession(trust_env=False, timeout=timeout) as session:
        for current_model in models_to_try:
            url = f"{BASE_GEMINI_URL}/{current_model}:generateContent?key={key}"
            for attempt in range(2):
                try:
                    async with session.post(
                        url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        proxy=proxy_url
                    ) as response:
                        status = response.status
                        response_text = await response.text()

                        if status == 200:
                            data = json.loads(response_text)
                            candidates = data.get("candidates", [])
                            if not candidates:
                                raise GeminiError("Google Gemini не вернул ответ (возможно, сработал фильтр безопасности).")

                            first_candidate = candidates[0]
                            parts = first_candidate.get("content", {}).get("parts", [])
                            reply_text = "".join(p.get("text", "") for p in parts if "text" in p)
                            if not reply_text:
                                raise GeminiError("Получен пустой ответ от модели.")
                            return reply_text.strip()

                        try:
                            err_data = json.loads(response_text)
                            err_msg = err_data.get("error", {}).get("message", response_text)
                        except Exception:
                            err_msg = response_text

                        if status in (503, 429) or "high demand" in err_msg.lower() or "quota" in err_msg.lower():
                            last_error_msg = f"Модель {current_model} временно занята ({status})."
                            await asyncio.sleep(0.5)
                            continue
                        elif status in (401, 403):
                            raise GeminiError("⛔ Неверный или заблокированный API ключ Google Gemini.")
                        else:
                            last_error_msg = f"Ошибка ({status}): {err_msg}"
                            break

                except asyncio.TimeoutError:
                    last_error_msg = f"Таймаут ожидания {current_model}."
                    await asyncio.sleep(0.5)
                except aiohttp.ClientError as e:
                    last_error_msg = f"Сетевая ошибка: {e}"
                    await asyncio.sleep(0.5)

    raise GeminiError(f"Серверы Google Gemini были временно перегружены. Попробуйте еще раз через пару секунд.")
