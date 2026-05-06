"""Environment-driven config for the SK signals bot."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    slack_signing_secret: str
    slack_bot_token: str
    target_channel_id: str
    target_emoji: str
    spider_api_key: str
    anthropic_api_key: str
    anthropic_model: str
    db_path: str
    port: int


def load_config() -> Config:
    return Config(
        slack_signing_secret=_required("SLACK_SIGNING_SECRET"),
        slack_bot_token=_required("SLACK_BOT_TOKEN"),
        target_channel_id=_required("SLACK_TARGET_CHANNEL_ID"),
        target_emoji=os.environ.get("SLACK_TARGET_EMOJI", "white_check_mark"),
        spider_api_key=_required("SPIDER_API_KEY"),
        anthropic_api_key=_required("ANTHROPIC_API_KEY"),
        anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        db_path=os.environ.get("DB_PATH", "/app/data/state.db"),
        port=int(os.environ.get("PORT", "8000")),
    )


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value
