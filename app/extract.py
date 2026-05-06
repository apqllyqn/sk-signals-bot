"""Pull LinkedIn profile URLs out of a Slack message."""

from __future__ import annotations

import re

# Slack auto-wraps links as <https://...|display> or <https://...>.
# Match either a wrapped URL or a bare URL.
_WRAPPED_PATTERN = re.compile(r"<(https?://[^|>\s]+)(?:\|[^>]*)?>")
_BARE_PATTERN = re.compile(r"https?://[^\s<>|()]+")
_LINKEDIN_HOST = re.compile(r"^https?://(?:[a-z0-9-]+\.)*linkedin\.com/", re.IGNORECASE)


def extract_linkedin_url(text: str) -> str | None:
    if not text:
        return None
    candidates: list[str] = []
    for m in _WRAPPED_PATTERN.finditer(text):
        candidates.append(m.group(1))
    cleaned = _WRAPPED_PATTERN.sub(" ", text)
    for m in _BARE_PATTERN.finditer(cleaned):
        candidates.append(m.group(0))

    for url in candidates:
        if _LINKEDIN_HOST.match(url):
            return url.rstrip(",.;)")
    return None
