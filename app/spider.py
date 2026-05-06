"""Spider.cloud scrape with LinkedIn-friendly defaults."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.spider.cloud"


async def scrape_linkedin(api_key: str, url: str, max_retries: int = 3) -> dict[str, Any]:
    """Scrape a LinkedIn URL using premium proxy + stealth + chrome rendering."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "url": url,
        "return_format": "markdown",
        "readability": True,
        "request": "smart",
        "premium_proxy": True,
        "stealth": True,
        "country_code": "US",
        "limit": 1,
    }
    last_err: Exception | None = None
    for i in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(f"{BASE_URL}/scrape", headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                result = data[0] if isinstance(data, list) and data else data or {}
                return result if isinstance(result, dict) else {}
        except httpx.HTTPStatusError as e:
            last_err = e
            if e.response.status_code == 429:
                wait = float(e.response.headers.get("retry-after", (i + 1) * 2.0))
                logger.warning("Spider 429, waiting %.1fs", wait)
                await asyncio.sleep(wait)
            elif e.response.status_code >= 500:
                await asyncio.sleep((i + 1) * 1.5)
            else:
                logger.warning("Spider HTTP %d for %s: %s", e.response.status_code, url, e.response.text[:200])
                return {}
        except httpx.RequestError as e:
            last_err = e
            logger.warning("Spider error: %s, retry %d/%d", e, i + 1, max_retries)
            await asyncio.sleep((i + 1) * 1.5)
    logger.error("Spider scrape failed after %d retries: %s", max_retries, last_err)
    return {}


def extract_content(scrape_result: dict) -> str:
    """Pull the markdown body out of a spider response, regardless of shape."""
    if not isinstance(scrape_result, dict):
        return ""
    for key in ("content", "markdown", "text", "body"):
        v = scrape_result.get(key)
        if isinstance(v, str) and v.strip():
            return v
    return ""
