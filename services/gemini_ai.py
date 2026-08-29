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
    Отправка текстового запроса или ведение диалога с Google Gemini (gemini-3.7-flash).
    Автоматически делает повторные попытки при временной нагрузке (503) и фолбэк на flash-latest.
    
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
    models_to_try = [preferred_model]
    for m in ["gemini-3.7-flash", "gemini-3.5-flash", "gemini-flash-latest"]:
        if m not in models_to_try:
            models_to_try.append(m)

    proxy_url = getattr(config, "PROXY_URL", None) or None

    contents: List[Dict[str, Any]] = []
    if history:
        contents.extend(history)

    contents.append({
        "role": "user",
        "parts": [{"text": prompt.strip()}]
    })

    payload: Dict[str, Any] = {
        "contents": contents
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

                        if status == 503 or "high demand" in err_msg.lower():
                            last_error_msg = f"Модель {current_model} временно перегружена (503)."
                            await asyncio.sleep(1.0)
                            continue
                        elif status == 429:
                            last_error_msg = "Превышен лимит запросов Google API (429)."
                            await asyncio.sleep(1.0)
                            continue
                        elif status in (401, 403):
                            raise GeminiError("⛔ Неверный или заблокированный API ключ Google Gemini.")
                        else:
                            last_error_msg = f"Ошибка ({status}): {err_msg}"
                            break

                except asyncio.TimeoutError:
                    last_error_msg = "Таймаут ожидания ответа от Google API."
                    await asyncio.sleep(1.0)
                except aiohttp.ClientError as e:
                    last_error_msg = f"Сетевая ошибка: {e}"
                    await asyncio.sleep(1.0)

    raise GeminiError(f"Не удалось получить ответ от Google Gemini: {last_error_msg}")
