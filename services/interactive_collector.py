from typing import List, Dict, Any
from .browser_resolver import resolve_url


async def resolve_urls_for_merchant(
    merchant: str,
    urls: List[str],
    click_texts: List[str] | None = None,
    wait_seconds: int = 8,
) -> List[Dict[str, Any]]:
    """
    Прогоняет список URL одного мерчанта через браузерный резолвер.
    Возвращает список словарей с результатами по каждому URL.
    """
    results: List[Dict[str, Any]] = []

    for url in urls:
        try:
            final_url, redirects = await resolve_url(
                url=url,
                wait_seconds=wait_seconds,
                click_texts=click_texts,
            )
            results.append(
                {
                    "merchant": merchant,
                    "start_url": url,
                    "final_url": final_url,
                    "redirects": redirects,
                    "ok": True,
                    "error": None,
                }
            )
        except Exception as e:
            results.append(
                {
                    "merchant": merchant,
                    "start_url": url,
                    "final_url": None,
                    "redirects": [],
                    "ok": False,
                    "error": str(e),
                }
            )

    return results
