# services/search.py
import httpx
from typing import List

from config import get_settings

settings = get_settings()

# Эндпоинт SerpAPI
SERP_API_URL = "https://serpapi.com/search"


async def search_google(merchant: str, keyword: str, country: str, limit: int = 20) -> List[str]:
    """
    Выполняет поиск в Google через SerpAPI и возвращает список URL из органической выдачи.
    """
    query = f"{merchant} {keyword}"

    params = {
        "q": query,
        "engine": "google",
        "google_domain": "google.com",
        "hl": "en",
        "gl": country.lower(),      # in, br, etc.
        "api_key": settings.serp_api_key,
        "num": limit,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(SERP_API_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    urls: List[str] = []
    for item in data.get("organic_results", []):
        url = item.get("link")
        if url:
            urls.append(url)

    return urls
