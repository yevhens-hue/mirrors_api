from typing import List, Optional
import asyncio

from fastapi import FastAPI, BackgroundTasks, Depends
from pydantic import BaseModel, HttpUrl

from db import get_db
from models import Mirror
from services.mirrors import (
    collect_mirrors_for_all,
    collect_mirrors_for_batch,
)

from services.browser_resolver import resolve_url as resolve_single_url
from services.interactive_collector import resolve_urls_for_merchant
from services.interactive_full import collect_mirrors_interactive_for_merchant


# =======================
#  СОЗДАЕМ ПРИЛОЖЕНИЕ
# =======================

app = FastAPI(title="Merchant mirrors API", version="0.6.0")


# =======================
#  УТИЛИТА: запуск async в BackgroundTasks
# =======================

def run_async(coro):
    """
    BackgroundTasks не await-ит корутины.
    Поэтому мы запускаем async-код через asyncio.run().
    """
    try:
        asyncio.run(coro)
    except RuntimeError:
        # Если loop уже существует (редко), используем новый loop вручную
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(coro)
        finally:
            loop.close()


# =====================================
#  НОВЫЕ ИНТЕРАКТИВНЫЕ ЭНДПОИНТЫ (Playwright)
# =====================================

class ResolveUrlRequest(BaseModel):
    url: HttpUrl
    wait_seconds: int = 8
    click_texts: List[str] | None = None


class ResolveUrlResponse(BaseModel):
    start_url: str
    final_url: str
    redirects: List[str]
    ok: bool
    error: str | None = None


class ResolveUrlBatchRequest(BaseModel):
    merchant: str
    urls: List[HttpUrl]
    wait_seconds: int = 8
    click_texts: List[str] | None = None


class ResolveUrlBatchResponseItem(BaseModel):
    merchant: str
    start_url: str
    final_url: str | None
    redirects: List[str]
    ok: bool
    error: str | None = None


@app.post(
    "/resolve_url",
    response_model=ResolveUrlResponse,
    summary="Resolve Url Endpoint",
)
async def resolve_url_endpoint(req: ResolveUrlRequest):
    """
    Открывает страницу через Playwright,
    отслеживает редиректы и пытается нажать типовые кнопки.
    """
    try:
        final_url, redirects = await resolve_single_url(
            url=str(req.url),
            wait_seconds=req.wait_seconds,
            click_texts=req.click_texts,
        )
        return ResolveUrlResponse(
            start_url=str(req.url),
            final_url=final_url,
            redirects=redirects,
            ok=True,
            error=None,
        )
    except Exception as e:
        return ResolveUrlResponse(
            start_url=str(req.url),
            final_url=str(req.url),
            redirects=[str(req.url)],
            ok=False,
            error=str(e),
        )


@app.post(
    "/resolve_url_batch",
    response_model=List[ResolveUrlBatchResponseItem],
    summary="Resolve Url Batch Endpoint",
)
async def resolve_url_batch_endpoint(req: ResolveUrlBatchRequest):
    """
    Прогоняет список URL одного мерчанта через Playwright.
    """
    results = await resolve_urls_for_merchant(
        merchant=req.merchant,
        urls=[str(u) for u in req.urls],
        click_texts=req.click_texts,
        wait_seconds=req.wait_seconds,
    )
    return results


# =====================================
#  FULL INTERACTIVE: merchant -> Serper -> Playwright
# =====================================

class CollectInteractiveRequest(BaseModel):
    merchant: str
    keywords: List[str]
    country: str = "in"
    lang: str = "en"
    limit: int = 10
    click_texts: List[str] | None = None
    wait_seconds: int = 8


@app.post(
    "/collect_mirrors_interactive",
    summary="Collect Mirrors Interactive",
)
async def collect_mirrors_interactive_endpoint(req: CollectInteractiveRequest):
    """
    Полный интерактивный сбор зеркал для одного мерчанта:
      1. Поиск доменов через Serper.dev
      2. Прогонка каждого URL через Playwright (клики, редиректы)
      3. Возвращаем финальный список зеркал
    """
    results = await collect_mirrors_interactive_for_merchant(
        merchant=req.merchant,
        keywords=req.keywords,
        country=req.country,
        lang=req.lang,
        limit=req.limit,
        click_texts=req.click_texts,
        wait_seconds=req.wait_seconds,
    )

    return {
        "ok": True,
        "merchant": req.merchant,
        "count": len(results),
        "items": results,
    }


# =======================================
#  BATCH / ALL + SYNC endpoint для диагностики
# =======================================

class BatchItem(BaseModel):
    merchant: str
    keywords: List[str]
    country: str = "in"
    lang: str = "en"
    limit: int = 10
    brand_pattern: Optional[str] = None


class CollectBatchRequest(BaseModel):
    items: List[BatchItem]


class CollectAllRequest(BaseModel):
    merchants: Optional[List[str]] = None  # сейчас в mirrors.py не используется
    limit: int = 10


@app.get("/health", summary="Health")
def health():
    return {"status": "ok"}


@app.post(
    "/collect_mirrors_all_async",
    summary="Collect Mirrors All Async",
)
def collect_mirrors_all_async_endpoint(
    req: CollectAllRequest,
    background_tasks: BackgroundTasks,
):
    background_tasks.add_task(run_async, collect_mirrors_for_all(limit=req.limit))
    return {"ok": True}


@app.post(
    "/collect_mirrors_batch",
    summary="Collect Mirrors Batch (async background)",
)
def collect_mirrors_batch_endpoint(
    req: CollectBatchRequest,
    background_tasks: BackgroundTasks,
):
    max_limit = max((item.limit for item in req.items), default=10)

    background_tasks.add_task(
        run_async,
        collect_mirrors_for_batch(
            items=req.items,
            limit=max_limit,
            follow_redirects=True,
        ),
    )
    return {"ok": True}


@app.post(
    "/collect_mirrors_batch_sync",
    summary="Collect Mirrors Batch (wait for result)",
)
async def collect_mirrors_batch_sync_endpoint(req: CollectBatchRequest):
    max_limit = max((item.limit for item in req.items), default=10)
    result = await collect_mirrors_for_batch(
        items=req.items,
        limit=max_limit,
        follow_redirects=True,
    )
    return result


# =======================================
#  /mirrors: фильтры + сортировка по свежести
# =======================================

@app.get(
    "/mirrors",
    summary="List Mirrors",
)
def list_mirrors(
    limit: int = 100,
    offset: int = 0,
    country: Optional[str] = None,
    merchant: Optional[str] = None,
    db=Depends(get_db),
):
    """
    Примеры:
      /mirrors?limit=100
      /mirrors?country=in&limit=100
      /mirrors?country=ar&merchant=stake&limit=100
      /mirrors?country=ar&limit=100&offset=100
    """
    query = db.query(Mirror)

    if country:
        query = query.filter(Mirror.country == country)

    if merchant:
        query = query.filter(Mirror.merchant == merchant)

    mirrors = (
        query.order_by(Mirror.last_seen_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return mirrors
