"""Background processing for a Slack ✅ reaction."""

from __future__ import annotations

import logging

from . import slack, spider, summarize
from .config import Config
from .extract import extract_linkedin_url
from .storage import ProcessedStore

logger = logging.getLogger(__name__)


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
            ":warning: No LinkedIn URL found in this message — nothing to scrape.",
        )
        return

    logger.info("Scraping %s for thread %s/%s", url, channel, message_ts)
    scrape_result = await spider.scrape_linkedin(cfg.spider_api_key, url)
    content = spider.extract_content(scrape_result)

    summary = await summarize.summarize_profile(
        cfg.anthropic_api_key, cfg.anthropic_model, url, content
    )

    header = f":mag: *Profile scrape:* <{url}>\n\n"
    await slack.post_thread_reply(cfg.slack_bot_token, channel, message_ts, header + summary)
    await slack.add_reaction(cfg.slack_bot_token, channel, message_ts, "robot_face")
