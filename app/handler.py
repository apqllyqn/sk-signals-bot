"""Background processing for a Slack ✅ reaction."""

from __future__ import annotations

import datetime
import logging
from pathlib import Path

from . import briefs, reps, research, slack, spider
from .config import Config
from .extract import extract_linkedin_url
from .storage import ProcessedStore

logger = logging.getLogger(__name__)

LINKEDIN_PROFILE_HINT = "/in/"


async def handle_reaction(
    cfg: Config,
    store: ProcessedStore,
    channel: str,
    message_ts: str,
    reactor_user_id: str = "",
) -> None:
    if not store.claim(channel, message_ts):
        logger.info("Already processed %s/%s, skipping", channel, message_ts)
        return

    msg = await slack.fetch_thread_root(cfg.slack_bot_token, channel, message_ts)
    if not msg:
        msg = await slack.fetch_message(cfg.slack_bot_token, channel, message_ts)
    if not msg:
        logger.warning("Could not fetch message %s/%s", channel, message_ts)
        return

    text = msg.get("text") or ""
    url = extract_linkedin_url(text)
    if not url:
        await slack.post_thread_reply(
            cfg.slack_bot_token,
            channel,
            message_ts,
            ":warning: No LinkedIn URL found in this message — nothing to research.",
        )
        return

    reps_dir = Path(__file__).resolve().parent.parent / "reps"
    rep = reps.load_rep_by_slack_id(reps_dir, reactor_user_id) if reactor_user_id else None
    rep_name = (rep or {}).get("meta", {}).get("name") or ""
    rep_tag = f" for *{rep_name}*" if rep_name else ""

    await slack.add_reaction(cfg.slack_bot_token, channel, message_ts, "hourglass_flowing_sand")
    await slack.post_thread_reply(
        cfg.slack_bot_token,
        channel,
        message_ts,
        f":mag: Running field recon on <{url}>{rep_tag} — searching the web, expect 2–4 min.",
    )

    scraped_md = ""
    if LINKEDIN_PROFILE_HINT in url:
        logger.info("Scraping %s", url)
        scrape_result = await spider.scrape_linkedin(cfg.spider_api_key, url)
        scraped_md = spider.extract_content(scrape_result)
    else:
        logger.info("Non-profile LinkedIn URL (%s); relying on web search only", url)

    parsed = await research.deep_research(
        cfg.anthropic_api_key, cfg.anthropic_model, url, scraped_md, rep=rep
    )

    title = parsed.get("title") or "Field Recon Brief"
    subtitle = parsed.get("subtitle") or ""
    tldr = parsed.get("tldr") or ""
    body_html = parsed.get("html_body") or "<p>(No content generated.)</p>"

    today = datetime.date.today().isoformat()
    html = briefs.render_html(
        title=title,
        subtitle=subtitle,
        linkedin_url=url,
        body_html=body_html,
        date=today,
    )
    slug = briefs.slug_for(url)
    briefs_dir = Path(cfg.db_path).parent / "briefs"
    briefs.save_brief(briefs_dir, slug, html)
    public_url = f"{cfg.public_base_url.rstrip('/')}/briefs/{slug}"

    msg_lines = [
        f":mag: *Field recon ready:* <{url}|{title}>",
        f"_{subtitle}_" if subtitle else "",
        f"> {tldr}" if tldr else "",
        f":scroll: Full brief: <{public_url}|signals-bot.hirecharm.com/briefs/{slug}>",
    ]
    slack_msg = "\n".join(line for line in msg_lines if line)

    await slack.post_thread_reply(cfg.slack_bot_token, channel, message_ts, slack_msg)
    await slack.add_reaction(cfg.slack_bot_token, channel, message_ts, "robot_face")
