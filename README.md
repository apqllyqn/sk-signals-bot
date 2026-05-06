# SK Signals Bot

Listens for `:white_check_mark:` reactions in the **#sk-live-signals** Slack channel.
When triggered on a message containing a LinkedIn URL, it scrapes the profile via
spider.cloud, summarizes it with Claude, and replies in the thread.

## Flow

```
reaction_added → verify Slack signature → ack 200 → background:
  fetch message → extract LinkedIn URL → spider.cloud /scrape (premium proxy + stealth)
  → Claude summary → chat.postMessage as thread reply
```

Idempotency: each `(channel, message_ts)` is claimed in SQLite so re-reactions don't repost.

## One-time Slack app setup

1. Create a new Slack app at https://api.slack.com/apps → "From scratch".
2. **OAuth & Permissions** → Bot Token Scopes: `channels:history`, `groups:history`,
   `chat:write`, `reactions:read`, `reactions:write`.
3. Install to workspace → copy the Bot User OAuth Token (`xoxb-...`) into `SLACK_BOT_TOKEN`.
4. **Basic Information** → copy the Signing Secret into `SLACK_SIGNING_SECRET`.
5. **Event Subscriptions** → enable, set Request URL to
   `https://<your-host>/slack/events`. Wait for the green check (URL verification).
6. Subscribe to bot event: `reaction_added`.
7. Reinstall the app (Slack will prompt) and invite the bot to `#sk-live-signals`:
   `/invite @<bot-name>`.
8. Get the channel ID: right-click channel → View channel details → bottom of the modal.
   Put it in `SLACK_TARGET_CHANNEL_ID`.

## Local run

```bash
cp .env.example .env  # fill in
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Expose with ngrok / cloudflared while testing the Events API URL.

## Deploy (Coolify)

Dockerfile builds a tiny Python 3.12 image, exposes port 8000, persistent volume at
`/app/data`. Configure env vars in Coolify, point a public URL at it, paste the URL
into Slack's Event Subscriptions.
