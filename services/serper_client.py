import os
from typing import List
import httpx


SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SERPER_URL = "https://google.serper.dev/search"


class SerperError(Exception):
    pass


async def search_domains(
    query: str,
    num: int = 10,
) -> List[str]:
    """
    Делает запрос в Serper.dev и возвращает список URL из органической выдачи.
    """
    if not SERPER_API_KEY:
        raise SerperError("SERPER_API_KEY is not set in environment")

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "q": query,
        "num": num,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(SERPER_URL, headers=headers, json=payload)
        if resp.status_code != 200:
            raise SerperError(f"Serper error {resp.status_code}: {resp.text}")

        data = resp.json()

    urls: List[str] = []
    for item in data.get("organic", []):
        url = item.get("link")
        if url:
            urls.append(url)

    return urls
