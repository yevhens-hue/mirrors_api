import socket
import ipaddress
import asyncio
from typing import List, Tuple
from urllib.parse import urlparse

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Defensive: Limit concurrent Chromium browser instances to prevent Fork Bomb DoS
BROWSER_SEMAPHORE = asyncio.Semaphore(3)

def is_safe_public_url(target_url: str) -> Tuple[bool, str]:
    """
    Validates that a URL does not point to internal, private, or loopback networks.
    Mitigates Server-Side Request Forgery (SSRF) and Cloud Metadata Exfiltration.
    """
    try:
        parsed = urlparse(target_url)
        if parsed.scheme not in ("http", "https"):
            return False, f"Invalid URL scheme: '{parsed.scheme}'. Only http and https allowed."
        
        hostname = parsed.hostname
        if not hostname:
            return False, "Empty or invalid hostname in URL."
        
        # Block known metadata hostnames and loopbacks
        if hostname.lower() in ("localhost", "127.0.0.1", "::1", "metadata.google.internal"):
            return False, f"Restricted destination hostname: {hostname}"

        # Resolve IP addresses for the hostname
        try:
            addr_info = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            return False, f"Could not resolve hostname: {hostname}"

        for entry in addr_info:
            ip_str = entry[4][0]
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or str(ip) in ("169.254.169.254", "0.0.0.0")
            ):
                return False, f"Destination IP {ip_str} is in a private/restricted address range (SSRF blocked)."

        return True, ""
    except Exception as e:
        return False, f"URL validation failed: {str(e)}"


async def resolve_url(
    url: str,
    wait_seconds: int = 8,
    click_texts: List[str] | None = None,
) -> Tuple[str, List[str]]:
    """
    Opens URL in Chromium safely, checks redirects, and attempts typical consent clicks.
    Enforces SSRF defense and concurrency limits.
    """
    is_safe, error_msg = is_safe_public_url(url)
    if not is_safe:
        raise ValueError(f"Security Alert: {error_msg}")

    click_texts = click_texts or ["Continue", "I agree", "Agree", "Accept", "Proceed"]
    redirects: List[str] = []

    async with BROWSER_SEMAPHORE:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context(
                ignore_https_errors=False,
                viewport={"width": 1280, "height": 800}
            )
            page = await context.new_page()

            # Track frame redirects safely with SSRF check on intermediate hops
            def on_navigate(frame):
                if frame.url and frame.url not in redirects:
                    safe_hop, _ = is_safe_public_url(frame.url)
                    if safe_hop:
                        redirects.append(frame.url)

            page.on("framenavigated", on_navigate)

            try:
                await page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=wait_seconds * 1000,
                )
            except PlaywrightTimeoutError:
                pass

            for text in click_texts:
                try:
                    btn = await page.query_selector(f"text={text}")
                    if btn:
                        await btn.click()
                        await page.wait_for_timeout(2000)
                        break
                except Exception:
                    pass

            final_url = page.url
            await browser.close()

    if not redirects:
        redirects.append(url)

    return final_url, redirects
