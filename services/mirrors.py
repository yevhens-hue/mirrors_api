import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from config import get_settings
from db import SessionLocal
from models import Mirror

settings = get_settings()


# ---------- Конфиг одного мерчанта ----------


@dataclass
class MerchantConfig:
    merchant: str
    country: str
    keywords: List[str]
    brand_pattern: Optional[str] = None


def get_default_merchants() -> List[MerchantConfig]:
    """
    Базовый список мерчантов для collect_mirrors_all_async.
    Можно потом вынести в отдельный JSON, но пока — жёстко в коде.
    """
    return [
        MerchantConfig(
            merchant="dafabet",
            country="in",
            keywords=["cricket betting", "sports betting"],
            brand_pattern="dafabet",
        ),
        MerchantConfig(
            merchant="1xbet",
            country="in",
            keywords=["cricket betting", "betting"],
            brand_pattern="1xbet",
        ),
        MerchantConfig(
            merchant="stake",
            country="in",
            keywords=["cricket betting", "sports"],
            brand_pattern="stake",
        ),
        MerchantConfig(
            merchant="1win",
            country="in",
            keywords=["cricket betting"],
            brand_pattern="1win",
        ),
        MerchantConfig(
            merchant="bc game",
            country="in",
            keywords=["cricket betting"],
            brand_pattern="bcgame",
        ),
    ]


# ---------- Serper.dev ----------


async def serper_search(
    query: str,
    *,
    num: int = 10,
    country: str = "in",
    lang: str = "en",
) -> List[str]:
    """
    Возвращает список URL-ов из Serper.dev.
    При любой ошибке (лимиты, сеть, 4xx/5xx) — просто [].
    """
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": settings.serper_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "q": query,
        "num": num,
        "gl": country,
        "hl": lang,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        # Если лимит, неверный ключ или сеть — просто ничего не вернём
        return []

    links: List[str] = []
    for item in data.get("organic", []):
        link = item.get("link")
        if link:
            links.append(link)

    return links


async def resolve_final_url(
    url: str,
    *,
    follow_redirects: bool = True,
) -> Tuple[str, str, bool]:
    """
    Возвращает (final_url, final_domain, is_redirector).
    Любая ошибка при запросе → считаем, что final_url = исходный url.
    """
    parsed = urlparse(url)
    start_domain = parsed.netloc.lower()

    if not follow_redirects:
        return url, start_domain, False

    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
            resp = await client.get(url)
            final_url = str(resp.url)
    except Exception:
        final_url = url

    final_domain = urlparse(final_url).netloc.lower()
    is_redirector = bool(final_domain) and final_domain != start_domain

    return final_url, final_domain, is_redirector


def is_mirror_domain(domain: str, brand_pattern: Optional[str]) -> bool:
    if not brand_pattern:
        return False
    return brand_pattern.lower() in domain.lower()


# ---------- Работа с БД ----------


def upsert_mirror(
    db: Session,
    *,
    merchant: str,
    country: str,
    keyword: str,
    source_url: str,
    source_domain: str,
    final_url: str,
    final_domain: str,
    is_redirector: bool,
    is_mirror: bool,
    cta_found: bool = False,
) -> Tuple[bool, bool]:
    """
    Создаёт или обновляет Mirror.
    Возвращает (created, updated).
    Любая ошибка commit → просто rollback и считаем, что ничего не поменялось.
    """
    now = datetime.utcnow()

    obj = (
        db.query(Mirror)
        .filter(
            Mirror.merchant == merchant,
            Mirror.country == country,
            Mirror.keyword == keyword,
            Mirror.source_url == source_url,
        )
        .first()
    )

    created = False
    updated = False

    if obj:
        obj.final_url = final_url
        obj.final_domain = final_domain
        obj.is_redirector = is_redirector
        obj.is_mirror = is_mirror
        obj.cta_found = cta_found
        obj.last_seen_at = now
        db.add(obj)
        updated = True
    else:
        obj = Mirror(
            merchant=merchant,
            country=country,
            keyword=keyword,
            source_url=source_url,
            source_domain=source_domain,
            final_url=final_url,
            final_domain=final_domain,
            is_redirector=is_redirector,
            is_mirror=is_mirror,
            cta_found=cta_found,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(obj)
        created = True

    try:
        db.commit()
    except Exception:
        db.rollback()
        # Если уникальный индекс или другая ошибка — просто считаем, что ничего не изменили
        created = False
        updated = False

    return created, updated


# ---------- Основная логика сбора ----------


async def _collect_for_config(
    cfg: MerchantConfig,
    *,
    limit: int,
    follow_redirects: bool,
) -> Tuple[int, int]:
    """
    Сбор зеркал для одного мерчанта (для всех его keywords).
    Любая ошибка в процессе — не роняет весь процесс, просто даёт меньше результатов.
    """
    created_total = 0
    updated_total = 0

    per_keyword_limit = max(1, limit // max(1, len(cfg.keywords)))

    db: Session = SessionLocal()
    try:
        for kw in cfg.keywords:
            if created_total + updated_total >= limit:
                break

            query = f"{cfg.merchant} {kw}"

            urls: List[str]
            try:
                urls = await serper_search(
                    query,
                    num=per_keyword_limit,
                    country=cfg.country,
                    lang="en",
                )
            except Exception:
                urls = []

            for url in urls:
                if created_total + updated_total >= limit:
                    break

                source_domain = urlparse(url).netloc.lower()

                try:
                    final_url, final_domain, is_redirector = await resolve_final_url(
                        url, follow_redirects=follow_redirects
                    )
                except Exception:
                    final_url = url
                    final_domain = source_domain
                    is_redirector = False

                mirror_flag = is_mirror_domain(final_domain, cfg.brand_pattern)

                created, updated = upsert_mirror(
                    db,
                    merchant=cfg.merchant,
                    country=cfg.country,
                    keyword=kw,
                    source_url=url,
                    source_domain=source_domain,
                    final_url=final_url,
                    final_domain=final_domain,
                    is_redirector=is_redirector,
                    is_mirror=mirror_flag,
                    cta_found=False,
                )
                created_total += int(created)
                updated_total += int(updated)

    finally:
        db.close()

    return created_total, updated_total


async def collect_mirrors_for_all(limit: int = 50) -> dict:
    """
    Массовый сбор по всем дефолтным мерчантам.
    Ошибки по отдельному мерчанту не роняют весь процесс.
    """
    configs = get_default_merchants()

    total_created = 0
    total_updated = 0

    for cfg in configs:
        try:
            c, u = await _collect_for_config(
                cfg,
                limit=limit,
                follow_redirects=False,  # для массового сбора без тяжёлых редиректов
            )
            total_created += c
            total_updated += u
        except Exception:
            # если с конкретным мерчантом всё плохо — просто пропускаем
            continue

    return {
        "status": "ok",
        "mode": "all",
        "created": total_created,
        "updated": total_updated,
        "merchants_count": len(configs),
        "limit": limit,
    }


async def collect_mirrors_for_batch(
    *,
    items: List,
    limit: int = 10,
    follow_redirects: bool = True,
) -> dict:
    """
    Сбор по конкретным мерчантам (как для /collect_mirrors_batch).
    Любые ошибки по отдельному мерчанту не роняют весь запрос.
    """
    configs: List[MerchantConfig] = []

    for item in items:
        # item может быть Pydantic-моделью или dict
        if hasattr(item, "dict"):
            data = item.dict()
        else:
            data = dict(item)

        configs.append(
            MerchantConfig(
                merchant=data["merchant"],
                country=data.get("country", "in"),
                keywords=data.get("keywords", []),
                brand_pattern=data.get("brand_pattern"),
            )
        )

    total_created = 0
    total_updated = 0

    for cfg in configs:
        try:
            c, u = await _collect_for_config(
                cfg,
                limit=limit,
                follow_redirects=follow_redirects,
            )
            total_created += c
            total_updated += u
        except Exception:
            # если с этим мерчантом что-то пошло не так — просто пропускаем
            continue

    return {
        "status": "ok",
        "mode": "batch",
        "created": total_created,
        "updated": total_updated,
        "merchants_count": len(configs),
        "limit": limit,
        "follow_redirects": follow_redirects,
    }
