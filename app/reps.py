"""Rep profile loader.

Each file under `reps/*.md` is a markdown brief with YAML frontmatter:

    ---
    slack_user_id: U07HAAGQFKM
    email: jay.gyuricza@stablekernel.com
    name: Jay Gyuricza
    first_name: Jay
    ---
    # ...body...

We match the Slack user_id who added the reaction against `slack_user_id` in the
frontmatter and return the parsed profile (frontmatter dict + body string).
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw_fm = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    fm: dict[str, str] = {}
    for line in raw_fm.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip()
    return fm, body


def load_rep_by_slack_id(reps_dir: Path, slack_user_id: str) -> dict | None:
    """Return {'meta': {...}, 'body': '...'} for the rep matching this Slack user_id, or None."""
    if not slack_user_id or not reps_dir.exists():
        return None
    for path in sorted(reps_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Failed reading %s: %s", path, e)
            continue
        meta, body = _parse_frontmatter(text)
        if meta.get("slack_user_id") == slack_user_id:
            logger.info("Matched reactor %s to rep %s", slack_user_id, path.name)
            return {"meta": meta, "body": body, "path": str(path)}
    logger.info("No rep profile found for Slack user_id %s", slack_user_id)
    return None
