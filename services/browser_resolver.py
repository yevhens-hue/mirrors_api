from typing import List, Tuple

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


async def resolve_url(
    url: str,
    wait_seconds: int = 8,
    click_texts: List[str] | None = None,
) -> Tuple[str, List[str]]:
    """
    Открывает URL в Chromium, отслеживает редиректы,
    пытается нажимать типовые кнопки.
    Возвращает (final_url, redirects_list).
    """
    click_texts = click_texts or ["Continue", "I agree", "Agree", "Accept", "Proceed"]

    redirects: List[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Собираем все переходы
        def on_navigate(frame):
            if frame.url and frame.url not in redirects:
                redirects.append(frame.url)

        page.on("framenavigated", on_navigate)

        # Переход на страницу
        try:
            await page.goto(
                url,
                wait_until="networkidle",
                timeout=wait_seconds * 1000,
            )
        except PlaywrightTimeoutError:
            # При таймауте просто продолжаем работать с тем,
            # что успели загрузить (частичный успех).
            pass

        # Пытаемся нажать типовые кнопки
        for text in click_texts:
            try:
                btn = await page.query_selector(f"text={text}")
                if btn:
                    await btn.click()
                    # дадим странице чуть времени после клика
                    await page.wait_for_timeout(3000)
                    break
            except Exception:
                # Любые ошибки клика игнорируем, задача — дойти до финального URL
                pass

        final_url = page.url
        await browser.close()

    # Если по какой-то причине навигации не было — вернём исходный URL
    if not redirects:
        redirects.append(url)

    return final_url, redirects
