from typing import List, Dict, Any

from .serper_client import search_domains
from .interactive_collector import resolve_urls_for_merchant


async def collect_mirrors_interactive_for_merchant(
    merchant: str,
    keywords: List[str],
    country: str = "in",
    lang: str = "en",
    limit: int = 10,
    click_texts: List[str] | None = None,
    wait_seconds: int = 8,
) -> List[Dict[str, Any]]:
    """
    Полный интерактивный цикл:
      1) Формируем поисковый запрос для Serper (мерчант + ключи + страна).
      2) Получаем кандидатов-URL из Serper.
      3) Прогоняем их через Playwright (клики, редиректы).
      4) Возвращаем результаты по каждому URL.
    """
    # Простейшая сборка поискового запроса
    parts: List[str] = [merchant] + keywords + [country]
    query = " ".join(parts)

    raw_urls = await search_domains(query=query, num=limit)

    if not raw_urls:
        return []

    results = await resolve_urls_for_merchant(
        merchant=merchant,
        urls=raw_urls,
        click_texts=click_texts,
        wait_seconds=wait_seconds,
    )

    # Можно добавить поле query для прозрачности
    for r in results:
        r["query"] = query

    return results
