"""Slack signature verification and Web API helpers."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time

import httpx

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api"


def verify_signature(signing_secret: str, timestamp: str, body: bytes, signature: str) -> bool:
    if not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > 60 * 5:
        return False
    base = b"v0:" + timestamp.encode() + b":" + body
    expected = "v0=" + hmac.new(signing_secret.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def fetch_message(bot_token: str, channel: str, ts: str) -> dict | None:
    """Fetch a single message via conversations.history (inclusive=true, latest=ts, limit=1)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{SLACK_API}/conversations.history",
            headers={"Authorization": f"Bearer {bot_token}"},
            params={"channel": channel, "latest": ts, "inclusive": "true", "limit": 1},
        )
        data = resp.json()
        if not data.get("ok"):
            logger.warning("Slack conversations.history failed: %s", data)
            return None
        messages = data.get("messages") or []
        return messages[0] if messages else None


async def fetch_thread_root(bot_token: str, channel: str, ts: str) -> dict | None:
    """If a reaction lands on a threaded reply, this fetches that exact message via replies."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{SLACK_API}/conversations.replies",
            headers={"Authorization": f"Bearer {bot_token}"},
            params={"channel": channel, "ts": ts, "inclusive": "true", "limit": 1},
        )
        data = resp.json()
        if not data.get("ok"):
            return None
        messages = data.get("messages") or []
        for m in messages:
            if m.get("ts") == ts:
                return m
        return messages[0] if messages else None


async def post_thread_reply(bot_token: str, channel: str, thread_ts: str, text: str) -> bool:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{SLACK_API}/chat.postMessage",
            headers={
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "channel": channel,
                "thread_ts": thread_ts,
                "text": text,
                "unfurl_links": False,
                "unfurl_media": False,
            },
        )
        data = resp.json()
        if not data.get("ok"):
            logger.warning("Slack chat.postMessage failed: %s", data)
            return False
        return True


async def add_reaction(bot_token: str, channel: str, ts: str, name: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                f"{SLACK_API}/reactions.add",
                headers={
                    "Authorization": f"Bearer {bot_token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json={"channel": channel, "timestamp": ts, "name": name},
            )
        except httpx.RequestError as e:
            logger.warning("reactions.add failed: %s", e)
