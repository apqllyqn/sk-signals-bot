"""Summarize a scraped LinkedIn profile into a prospect-qualification snippet."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = """You analyze scraped LinkedIn profiles for an outbound sales team.

Output a tight Slack-flavored summary with these sections, in this exact order, using bold labels:

*Name & Title:* Full name, current role, company.
*Tenure & Background:* Time in role + 1-line career arc (prior companies, total YOE, any pattern).
*Current Focus:* What their current role/company is doing (1-2 lines from the profile).
*Recent Activity:* Up to 3 bullets of posts, comments, or signals visible in the scrape. If none, say "No public activity found in scrape."
*Outreach Hooks:* 2-3 bullets — concrete angles a rep could open with. Each hook must reference a specific fact from the scrape.
*Risk Flags:* Anything that suggests bad fit (e.g. just left, not in target ICP, too senior/junior). Say "None obvious." if clean.

Rules:
- Be specific. Every claim must be grounded in the scraped text.
- No fluff, no marketing language, no "this person seems passionate about..."
- Use Slack mrkdwn: *bold* (single asterisks), bullets as `• `.
- Keep total output under 1500 characters.
- If the scrape is mostly empty / blocked / login-walled, say so plainly in one line and stop."""


async def summarize_profile(api_key: str, model: str, url: str, scraped_markdown: str) -> str:
    if not scraped_markdown.strip():
        return f":warning: Spider returned empty content for {url}. LinkedIn likely blocked the scrape."

    user_msg = (
        f"LinkedIn URL: {url}\n\n"
        f"Scraped content (markdown):\n---\n{scraped_markdown[:18000]}\n---"
    )

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_msg}],
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(ANTHROPIC_API, headers=headers, json=payload)
        if resp.status_code != 200:
            logger.warning("Anthropic %d: %s", resp.status_code, resp.text[:300])
            return f":warning: Summary generation failed (HTTP {resp.status_code})."
        data = resp.json()
        blocks = data.get("content") or []
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
        return text or ":warning: Empty summary returned."
