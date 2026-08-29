import asyncio
import logging
import random
import urllib.parse
from typing import List, Optional, Tuple
import aiohttp

logger = logging.getLogger(__name__)

class FluxError(Exception):
    """Исключение для ошибок генерации изображений FLUX."""
    pass

async def generate_flux_image(
    prompt: str,
    seed: Optional[int] = None,
    width: int = 1024,
    height: int = 1024
) -> bytes:
    """
    Генерация одного изображения с использованием модели FLUX / Turbo с интеллектуальным фолбэком.
    
    :param prompt: Текстовый промпт.
    :param seed: Сид для воспроизводимости/вариативности.
    :param width: Ширина изображения.
    :param height: Высота изображения.
    :return: Бинарные данные изображения (JPEG/PNG bytes).
    """
    if not prompt or not prompt.strip():
        raise FluxError("Промпт не может быть пустым.")

    current_seed = seed if seed is not None else random.randint(1, 99999999)
    encoded_prompt = urllib.parse.quote(prompt.strip())

    candidate_urls = [
        f"https://image.pollinations.ai/prompt/{encoded_prompt}?model=flux&nologo=true&seed={current_seed}&width={width}&height={height}",
        f"https://image.pollinations.ai/prompt/{encoded_prompt}?model=turbo&nologo=true&seed={current_seed}&width={width}&height={height}",
        f"https://image.pollinations.ai/prompt/{encoded_prompt}?nologo=true&seed={current_seed}&width={width}&height={height}"
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "image/*"
    }

    timeout = aiohttp.ClientTimeout(total=15, connect=5)
    last_error = None

    async with aiohttp.ClientSession(trust_env=False, timeout=timeout) as session:
        for url in candidate_urls:
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        if len(data) > 1000:
                            return data
                    elif resp.status == 429:
                        last_error = "Лимит очереди сервера (429)"
                        await asyncio.sleep(0.3)
                        continue
                    else:
                        last_error = f"HTTP {resp.status}"
            except asyncio.TimeoutError:
                last_error = "Превышено время ожидания"
            except Exception as e:
                last_error = str(e)

    raise FluxError(f"Не удалось получить изображение: {last_error}")

async def generate_flux_images(
    prompt: str,
    count: int = 1
) -> Tuple[List[bytes], List[str]]:
    """
    Генерация от 1 до 4 изображений FLUX.
    
    :param prompt: Текстовый промпт.
    :param count: Количество изображений (1..4).
    :return: Кортеж (список сгенерированных картинок в байтах, список ошибок).
    """
    count = max(1, min(count, 4))
    images: List[bytes] = []
    errors: List[str] = []

    for i in range(count):
        if i > 0:
            await asyncio.sleep(0.3)
        seed = random.randint(1, 99999999) + i * 137
        try:
            img = await generate_flux_image(prompt=prompt, seed=seed)
            images.append(img)
        except Exception as e:
            errors.append(str(e))

    return images, errors
