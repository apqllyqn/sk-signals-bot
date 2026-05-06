"""Deep field-recon research using Claude with native web_search.

Produces output modeled on the Mennen Field Recon Brief
(see ../reference/mennen-field-recon-brief.md).
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = """You are an outbound-sales field analyst for Stable Kernel / Charm.
You produce a "Field Recon Brief" on a single executive — the kind of brief that wins meetings because it proves the rep read past the headlines.

You will be given:
1. A LinkedIn profile URL.
2. The scraped markdown of that profile (may be partial or paywalled).

Your job: research aggressively using the web_search tool, then output a structured brief.

## Required research passes (use web_search liberally — 8 to 15 searches is normal)

- "{name}" + current company + "Chief Digital" / CIO / CTO etc.
- "{name}" + "{prior company}" — confirm history
- "{name}" + "interview" / "podcast" / "keynote" / "speaker"
- "{name}" + "board" / "director" / "advisor"
- "{current company}" + recent press releases, earnings, vendor announcements, Project Catalyst-style strategy launches
- "{current company}" + "AI" / "loyalty" / "POS" / "kiosk" / "digital transformation"
- "{current company}" + leadership team (CEO, COO, CMO, peers)
- conferences he's likely to attend (NRF, FSTEC, Constellation BT150, Evanta, industry-specific)
- physical locations — flagship stores, innovation labs, HQ
- recent LinkedIn hiring posts → identify the recruiter (warm-path amplifier)

## Output format — emit exactly these sections, in this order, as Slack mrkdwn

Use *bold* (single asterisks), `> ` for quote lines, and `• ` for bullets. Embed clickable URLs as `<url|short label>` only when truly load-bearing — do not link every word.

```
*Field Recon Brief — {Full Name}* ({current title}, {current company})
_Compiled {today's date}. LinkedIn:_ <{linkedin_url}|profile>

*Where they'll physically be*
• CONFIRMED: …
• LIKELY: …

*Physical footprint*
(named locations, innovation labs, flagship stores, HQ vs hybrid)

*Recent media (last ~12mo)*
(publications + key quote/framing + dates; cite the publication name in bold)

*LinkedIn engagement signals*
(what they post about, who amplifies them, warm-path entry points)

*Inner circle*
(named CEO, peers, recruiter — with one-line context per name)

*Vendor / stack signals*
(named tools, partners, RFPs, gaps. Call out OPEN RFP slots explicitly when no vendor is publicly named.)

*Board / advisory*
(public boards, audit/gov committees, current crises if applicable)

*Personal / civic*
(alma mater boards, NACD, charity, sports, etc.)

*Highest-leverage outreach hooks (ranked)*
1. …
2. …
3. …
(2–6 hooks. Each must reference a specific fact from the research, with a one-line "why this works" tail.)
```

## Hard rules

- Every claim must trace to a specific source you saw in web_search results or the LinkedIn scrape. If you can't source it, drop it. Do not invent.
- Distinguish CONFIRMED vs LIKELY clearly. "Likely" claims need a reason ("he spoke there at his prior role").
- Call out OPEN RFP / OPEN VENDOR SLOTS explicitly — these are the most valuable hooks.
- Identify the warm-path amplifier (recruiter, peer who reposts) — this is often more useful than cold-DMing the target.
- No marketing fluff, no "passionate about innovation." Plain, specific, sourced.
- If LinkedIn scrape is empty/blocked AND web search returns no useful hits, say so plainly in one paragraph and stop. Do NOT pad.
- Stay under ~6000 characters total.
"""


async def deep_research(
    api_key: str,
    model: str,
    linkedin_url: str,
    scraped_markdown: str,
    max_search_uses: int = 15,
    timeout_s: float = 600.0,
) -> str:
    """Run agentic web-search research and return the Slack-formatted brief.

    Uses Anthropic's server-side web_search tool, so we get the final
    answer in one round-trip even though Claude may run many searches.
    """
    user_msg = (
        f"LinkedIn URL: {linkedin_url}\n\n"
        f"LinkedIn scrape (may be partial):\n---\n{scraped_markdown[:18000]}\n---\n\n"
        "Research this person aggressively with web_search, then output the Field Recon Brief."
    )

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 4096,
        "system": SYSTEM_PROMPT,
        "tools": [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": max_search_uses,
            }
        ],
        "messages": [{"role": "user", "content": user_msg}],
    }

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        resp = await client.post(ANTHROPIC_API, headers=headers, json=payload)
        if resp.status_code != 200:
            logger.warning("Anthropic %d: %s", resp.status_code, resp.text[:500])
            return f":warning: Research call failed (HTTP {resp.status_code}). {resp.text[:300]}"
        data = resp.json()

    # The content array is a mix of web_search_tool_use, web_search_tool_result, text, etc.
    # We just want the final text the model emitted.
    blocks = data.get("content") or []
    text_parts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
    final_text = "\n\n".join(t for t in text_parts if t).strip()

    # Count searches used for logging.
    n_searches = sum(1 for b in blocks if b.get("type") == "server_tool_use")
    logger.info("Research used %d web searches; output %d chars", n_searches, len(final_text))

    return final_text or ":warning: Empty research output."
