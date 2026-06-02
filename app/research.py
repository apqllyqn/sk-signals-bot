"""Deep field-recon research using Claude with native web_search.

Output: HTML body + a one-line Slack TLDR, parsed from a sentinel-delimited response.
Modeled on the Mennen Field Recon Brief (see ../reference/mennen-field-recon-brief.md).
"""

from __future__ import annotations

import logging
import re

import httpx

logger = logging.getLogger(__name__)

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"

TLDR_DELIM = "===TLDR==="
TITLE_DELIM = "===TITLE==="
SUBTITLE_DELIM = "===SUBTITLE==="
HTML_DELIM = "===HTML==="

SYSTEM_PROMPT = f"""You are an outbound-sales field analyst for Stable Kernel / Charm.
You produce a "Field Recon Brief" on a single executive — the kind of brief that wins meetings because it proves the rep read past the headlines.

You will be given:
1. A LinkedIn profile URL.
2. The scraped markdown of that profile (may be partial or paywalled).

Your job:

## STEP 1 — Research aggressively with web_search (8 to 15 searches is normal)

Use web_search for ALL of the following passes:
- "{{name}}" + current company + role keywords (CIO, CTO, Chief Digital, etc.)
- "{{name}}" + each prior company — confirm the career arc
- "{{name}}" + "interview" / "podcast" / "keynote" / "speaker"
- "{{name}}" + "board" / "director" / "advisor"
- "{{current company}}" + recent press releases, earnings, vendor announcements, named strategic initiatives
- "{{current company}}" + "AI" / "loyalty" / "POS" / "kiosk" / "digital transformation" (or industry analogs)
- "{{current company}}" leadership team — find CEO, COO, CMO, peers
- conferences they're likely to attend (NRF, FSTEC, Constellation BT150, Evanta, industry-specific)
- physical locations — flagship stores, innovation labs, HQ

## STEP 2 — Find LinkedIn URLs for every named person

CRITICAL: For every person you name in the brief (CEO, peers, recruiter, board chair, predecessor, etc.), use web_search to find their `linkedin.com/in/...` URL with a query like `"<full name>" "<company>" linkedin`. Embed those URLs as `<a href="...">name</a>` links inline in the HTML. If you cannot find a LinkedIn URL after one focused search, link to a Google search for them instead — never invent a URL.

## STEP 3 — Output exactly this structure, in this exact order, using the sentinel delimiters

{TITLE_DELIM}
<Full Name>

{SUBTITLE_DELIM}
<Current Title>, <Current Company>

{TLDR_DELIM}
<single sentence, max 200 chars, the most actionable one-liner — name the highest-leverage outreach hook>

{HTML_DELIM}
<HTML body — see schema below>

## HTML body schema

Emit semantic HTML using only these tags: h2, h3, p, ul, ol, li, a, strong, em, blockquote, span, code, table, thead, tbody, tr, th, td. NO <html>, <head>, <body>, <style>, <script>, <img>, or <div>. The wrapper template provides all layout and CSS.

Use these CSS classes when they apply:
- `<span class="pill confirmed">CONFIRMED</span>` for confirmed presence at events
- `<span class="pill likely">LIKELY</span>` for likely-but-unconfirmed
- `<span class="pill open">OPEN RFP</span>` for vendor slots they haven't named publicly

Required sections, in order, each starting with an `<h2>`:

1. `<h2>Where they'll physically be</h2>` — bulleted list. Lead with confirmed (with the `pill confirmed` span) then likely (with `pill likely`). Cite the source for each via inline `<a>`. Always say WHY a "likely" event is likely.
2. `<h2>Physical footprint</h2>` — flagships, innovation labs, HQ, hybrid pattern.
3. `<h2>Recent media (last ~12mo)</h2>` — bulleted, each item: <strong>Publication</strong> + date + key quote/framing + linked headline.
4. `<h2>LinkedIn engagement signals</h2>` — what they post about, who amplifies them, the warm-path entry point (often a recruiter or peer who reposts).
5. `<h2>Inner circle</h2>` — table with columns Name | Role | Why they matter. Every name MUST be a linked `<a href="linkedin.com/in/...">` resolved via web_search.
6. `<h2>Vendor / stack signals</h2>` — list named vendors and what they do. Use `<span class="pill open">OPEN RFP</span>` when a category is publicly mentioned but no vendor is named — these are the highest-value hooks.
7. `<h2>Board / advisory</h2>` — public boards, audit/gov roles, current dynamics worth knowing.
8. `<h2>Personal / civic</h2>` — alma mater boards, NACD, charity, sports. Skip if nothing found.
9. `<h2>Highest-leverage outreach hooks</h2>` — ordered list, 2 to 6 hooks. Each `<li>`: a one-line hook in <strong>, then a one-sentence "why this works" tail referencing the specific fact it builds on.
10. **(REP-SPECIFIC, conditional)** If a `<REP_CONTEXT>` block is supplied in the user message, add a section `<h2>Your specific angles — {{Rep First Name}}</h2>` BEFORE the "Reach out to" table. This section is the whole reason the rep reacted to the post — it is the most important section in the brief when present. Produce 3 to 6 `<li>` bullets in an `<ol>`. Each bullet MUST cross-reference one concrete signal about the prospect (from your research above) with one concrete fact about the rep (from `<REP_CONTEXT>` — a past account, a past role, an alma mater, a city, a category of work they scaled, an acquisition they lived through). Lead each `<li>` with a one-line angle in `<strong>`, then a one-sentence "why this works for {{Rep First Name}} specifically" tail that names BOTH the prospect signal AND the rep fact you crossed it with. Hard rule: never invent a rep fact — only use what's in `<REP_CONTEXT>`. If you cannot find at least 2 honest cross-references after trying, omit this entire section rather than pad. If `<REP_CONTEXT>` is NOT supplied, skip this section entirely.
11. `<h2>Reach out to</h2>` — a final ranked table with columns Name | Role | LinkedIn | Why first. List 3 to 8 people in priority order, with the warmest path first (often the recruiter or a peer who reposts), the target themselves second, and any decision-influencers after. Every LinkedIn cell must contain a real linkedin.com/in/ URL you found via web_search; if you couldn't find one, write "—" plain.

## Hard rules

- Every claim must trace to a source you saw in web_search results or the LinkedIn scrape. If you can't source it, drop it. Do not invent.
- Distinguish CONFIRMED vs LIKELY clearly. Likely claims need a one-line reason.
- Call out OPEN RFP / OPEN VENDOR SLOTS explicitly — these are the highest-value hooks.
- Identify the warm-path amplifier (recruiter, peer who reposts) — often more useful than cold-DMing the target.
- No marketing fluff, no "passionate about innovation." Plain, specific, sourced.
- If LinkedIn scrape is empty/blocked AND web search returns no useful hits, emit a brief HTML body explaining what was attempted and stop. Do NOT pad.
- Aim for 1500–4000 words of HTML body content. Quality over quantity.
"""


def parse_response(text: str) -> dict:
    """Split the model's text into title / subtitle / tldr / html_body."""
    out = {"title": "", "subtitle": "", "tldr": "", "html_body": ""}

    def _section(name: str) -> str:
        m = re.search(rf"{re.escape(name)}\s*\n(.*?)(?=\n===[A-Z]+===|\Z)", text, re.S)
        return m.group(1).strip() if m else ""

    out["title"] = _section(TITLE_DELIM)
    out["subtitle"] = _section(SUBTITLE_DELIM)
    out["tldr"] = _section(TLDR_DELIM)
    out["html_body"] = _section(HTML_DELIM)
    return out


async def deep_research(
    api_key: str,
    model: str,
    linkedin_url: str,
    scraped_markdown: str,
    max_search_uses: int = 15,
    timeout_s: float = 600.0,
    rep: dict | None = None,
) -> dict:
    """Run agentic web-search research. Returns dict with title/subtitle/tldr/html_body.

    If `rep` is provided (dict with `meta` + `body` from app.reps), inject a
    REP_CONTEXT block so the model produces the "Your specific angles" section.
    """
    rep_block = ""
    if rep:
        meta = rep.get("meta") or {}
        rep_block = (
            "\n\n<REP_CONTEXT>\n"
            f"Rep name: {meta.get('name', '')}\n"
            f"Rep first name: {meta.get('first_name', '')}\n"
            f"Rep title: {meta.get('title', '')} @ {meta.get('company', '')}\n\n"
            f"{rep.get('body', '')}\n"
            "</REP_CONTEXT>\n\n"
            "This rep reacted to the prospect's LinkedIn post — that is the signal that surfaced this brief. "
            "You MUST produce the rep-specific \"Your specific angles\" section per the schema above, "
            "crossing the prospect's research with REP_CONTEXT. Never invent a rep fact."
        )

    user_msg = (
        f"LinkedIn URL: {linkedin_url}\n\n"
        f"LinkedIn scrape (may be partial):\n---\n{scraped_markdown[:18000]}\n---"
        f"{rep_block}\n\n"
        "Research aggressively with web_search (including LinkedIn URLs for every named person), "
        "then output the Field Recon Brief using the sentinel-delimited format."
    )

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 8192,
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
            return {
                "title": "Research failed",
                "subtitle": "",
                "tldr": f"Research call failed (HTTP {resp.status_code}).",
                "html_body": f"<p>Research call failed (HTTP {resp.status_code}).</p><pre>{resp.text[:500]}</pre>",
            }
        data = resp.json()

    blocks = data.get("content") or []
    text_parts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
    final_text = "\n".join(t for t in text_parts if t).strip()

    n_searches = sum(1 for b in blocks if b.get("type") == "server_tool_use")
    logger.info("Research used %d searches; raw output %d chars", n_searches, len(final_text))

    parsed = parse_response(final_text)
    if not parsed["html_body"]:
        # Fallback: model didn't follow the delimiter format.
        parsed["html_body"] = f"<pre>{final_text}</pre>"
        if not parsed["title"]:
            parsed["title"] = "Field Recon Brief"
        if not parsed["tldr"]:
            parsed["tldr"] = "Brief generated (delimiter parse failed — see HTML)."
    return parsed
