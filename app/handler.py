"""Background processing for a Slack ✅ reaction."""

from __future__ import annotations

import logging

from . import research, slack, spider
from .config import Config
from .extract import extract_linkedin_url
from .storage import ProcessedStore

logger = logging.getLogger(__name__)

LINKEDIN_PROFILE_HINT = "/in/"


async def handle_reaction(cfg: Config, store: ProcessedStore, channel: str, message_ts: str) -> None:
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

    # Acknowledge fast so the user knows the bot took the job.
    await slack.add_reaction(cfg.slack_bot_token, channel, message_ts, "hourglass_flowing_sand")
    await slack.post_thread_reply(
        cfg.slack_bot_token,
        channel,
        message_ts,
        f":mag: Running field recon on <{url}> — searching the web, expect 2–4 min.",
    )

    scraped_md = ""
    if LINKEDIN_PROFILE_HINT in url:
        logger.info("Scraping %s", url)
        scrape_result = await spider.scrape_linkedin(cfg.spider_api_key, url)
        scraped_md = spider.extract_content(scrape_result)
    else:
        # Job posting / company page — skip the LinkedIn scrape, let web search do all the work.
        logger.info("Non-profile LinkedIn URL (%s); relying on web search only", url)

    brief = await research.deep_research(
        cfg.anthropic_api_key, cfg.anthropic_model, url, scraped_md
    )

    await slack.post_thread_reply(cfg.slack_bot_token, channel, message_ts, brief)
    await slack.add_reaction(cfg.slack_bot_token, channel, message_ts, "robot_face")
