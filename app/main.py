"""FastAPI entrypoint. Listens for Slack reaction_added events and dispatches scrapes."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from . import briefs
from .config import load_config
from .handler import handle_reaction
from .slack import verify_signature
from .storage import ProcessedStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("sk-signals-bot")

cfg = load_config()
store = ProcessedStore(cfg.db_path)
app = FastAPI(title="SK Signals Bot")


@app.get("/health")
async def health():
    return {"ok": True}


BRIEFS_DIR = Path(cfg.db_path).parent / "briefs"


@app.get("/briefs/{slug}", response_class=HTMLResponse)
async def serve_brief(slug: str):
    html = briefs.load_brief(BRIEFS_DIR, slug)
    if html is None:
        raise HTTPException(status_code=404, detail="brief not found")
    return HTMLResponse(content=html)


@app.post("/slack/events")
async def slack_events(
    request: Request,
    background: BackgroundTasks,
    x_slack_signature: str | None = Header(default=None),
    x_slack_request_timestamp: str | None = Header(default=None),
):
    body = await request.body()
    if not verify_signature(
        cfg.slack_signing_secret,
        x_slack_request_timestamp or "",
        body,
        x_slack_signature or "",
    ):
        raise HTTPException(status_code=401, detail="bad signature")

    payload = await request.json()

    # URL verification handshake (one-time when configuring the Events API)
    if payload.get("type") == "url_verification":
        return PlainTextResponse(payload.get("challenge", ""))

    if payload.get("type") != "event_callback":
        return JSONResponse({"ok": True})

    event = payload.get("event") or {}
    if event.get("type") != "reaction_added":
        return JSONResponse({"ok": True})

    if event.get("reaction") != cfg.target_emoji:
        return JSONResponse({"ok": True})

    item = event.get("item") or {}
    if item.get("type") != "message":
        return JSONResponse({"ok": True})

    channel = item.get("channel")
    message_ts = item.get("ts")
    if channel != cfg.target_channel_id or not message_ts:
        return JSONResponse({"ok": True})

    background.add_task(_run_handler, channel, message_ts)
    return JSONResponse({"ok": True})


async def _run_handler(channel: str, message_ts: str):
    try:
        await handle_reaction(cfg, store, channel, message_ts)
    except Exception:
        logger.exception("handler failed for %s/%s", channel, message_ts)
