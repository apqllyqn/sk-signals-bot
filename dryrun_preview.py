"""Local dry-run: simulate Jay reacting to a LinkedIn URL.

Runs spider scrape + Claude deep_research with Jay's rep profile loaded,
then renders + saves the HTML brief to briefs-preview/.
Same code path as production, just bypasses Slack.
"""

from __future__ import annotations

import asyncio
import datetime
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import briefs, reps, research, spider


SPIDER_KEY = os.environ["SPIDER_API_KEY"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

REACTOR_USER_ID = "U07HAAGQFKM"  # Jay
URL = "https://www.linkedin.com/in/vadim-parizher-a092a33/"


async def main() -> None:
    here = Path(__file__).resolve().parent
    reps_dir = here / "reps"
    rep = reps.load_rep_by_slack_id(reps_dir, REACTOR_USER_ID)
    print(f"[dryrun] reactor={REACTOR_USER_ID} -> rep={(rep or {}).get('meta', {}).get('name')}")

    print(f"[dryrun] spider scrape: {URL}")
    scrape_result = await spider.scrape_linkedin(SPIDER_KEY, URL)
    scraped_md = spider.extract_content(scrape_result)
    print(f"[dryrun] scrape chars: {len(scraped_md)}")

    print(f"[dryrun] deep_research model={MODEL}")
    parsed = await research.deep_research(
        ANTHROPIC_KEY, MODEL, URL, scraped_md, rep=rep
    )

    title = parsed.get("title") or "Field Recon Brief"
    subtitle = parsed.get("subtitle") or ""
    tldr = parsed.get("tldr") or ""
    body_html = parsed.get("html_body") or "<p>(empty)</p>"

    today = datetime.date.today().isoformat()
    html = briefs.render_html(
        title=title,
        subtitle=subtitle,
        linkedin_url=URL,
        body_html=body_html,
        date=today,
    )

    out_dir = here / "briefs-preview"
    slug = briefs.slug_for(URL)
    saved = briefs.save_brief(out_dir, slug, html)

    print(f"\n[dryrun] TITLE: {title}")
    print(f"[dryrun] SUBTITLE: {subtitle}")
    print(f"[dryrun] TLDR: {tldr}")
    print(f"[dryrun] brief saved: {saved}")


if __name__ == "__main__":
    asyncio.run(main())
