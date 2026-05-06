"""Persist and serve generated Field Recon Briefs as HTML pages."""

from __future__ import annotations

import hashlib
import re
import time
from html import escape
from pathlib import Path

BRIEF_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Field Recon Brief</title>
<meta name="robots" content="noindex,nofollow">
<style>
  :root {{
    --bg: #fafaf7;
    --ink: #1a1a1a;
    --muted: #5b5b58;
    --rule: #d8d6cf;
    --accent: #b8331a;
    --code-bg: #f0eee7;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--ink);
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
    font-size: 17px;
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
  }}
  .wrap {{
    max-width: 760px;
    margin: 0 auto;
    padding: 56px 28px 96px;
  }}
  header.kicker {{
    border-bottom: 1px solid var(--rule);
    padding-bottom: 20px;
    margin-bottom: 28px;
  }}
  header.kicker .label {{
    font-family: "SF Mono", ui-monospace, "Menlo", monospace;
    font-size: 11px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 6px;
  }}
  header.kicker h1 {{
    font-size: 34px;
    line-height: 1.15;
    margin: 0 0 4px 0;
    font-weight: 600;
    letter-spacing: -0.01em;
  }}
  header.kicker .sub {{
    color: var(--muted);
    font-size: 16px;
  }}
  header.kicker .meta {{
    margin-top: 10px;
    font-family: "SF Mono", ui-monospace, "Menlo", monospace;
    font-size: 12px;
    color: var(--muted);
  }}
  header.kicker .meta a {{ color: var(--muted); }}
  h2 {{
    font-size: 13px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    font-family: "SF Mono", ui-monospace, "Menlo", monospace;
    margin: 36px 0 14px;
    color: var(--accent);
    border-top: 1px solid var(--rule);
    padding-top: 22px;
  }}
  h3 {{
    font-size: 18px;
    margin: 18px 0 6px;
    font-weight: 600;
  }}
  p, li {{ margin: 0 0 10px; }}
  ul, ol {{ padding-left: 22px; }}
  ul li::marker {{ color: var(--accent); }}
  ol li::marker {{ color: var(--accent); font-weight: 600; }}
  a {{ color: var(--accent); text-decoration: underline; text-underline-offset: 2px; }}
  a:hover {{ text-decoration-thickness: 2px; }}
  blockquote {{
    border-left: 3px solid var(--accent);
    padding: 4px 14px;
    margin: 12px 0;
    color: var(--muted);
    font-style: italic;
  }}
  code, .mono {{
    font-family: "SF Mono", ui-monospace, "Menlo", monospace;
    background: var(--code-bg);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 0.92em;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 15px;
  }}
  th, td {{
    text-align: left;
    padding: 8px 10px;
    border-bottom: 1px solid var(--rule);
    vertical-align: top;
  }}
  th {{ color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }}
  .pill {{
    display: inline-block;
    padding: 1px 8px;
    border-radius: 999px;
    font-family: "SF Mono", ui-monospace, "Menlo", monospace;
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    background: var(--code-bg);
    color: var(--muted);
  }}
  .pill.confirmed {{ background: #1a1a1a; color: #fafaf7; }}
  .pill.likely {{ background: #f4ddd6; color: var(--accent); }}
  .pill.open {{ background: var(--accent); color: #fafaf7; }}
  footer {{
    margin-top: 56px;
    padding-top: 18px;
    border-top: 1px solid var(--rule);
    color: var(--muted);
    font-size: 12px;
    font-family: "SF Mono", ui-monospace, "Menlo", monospace;
  }}
</style>
</head>
<body>
<div class="wrap">
  <header class="kicker">
    <div class="label">Field Recon Brief</div>
    <h1>{title}</h1>
    <div class="sub">{subtitle}</div>
    <div class="meta">
      Compiled {date} ·
      <a href="{linkedin_url}" target="_blank" rel="noopener">LinkedIn profile</a>
    </div>
  </header>
  {body}
  <footer>SK Signals Bot · #sk-live-signals · {date}</footer>
</div>
</body>
</html>
"""


def slug_for(linkedin_url: str) -> str:
    """jmennen-a3f9c2 — derived from the URL handle plus a short timestamp hash."""
    handle_match = re.search(r"/in/([^/?#]+)", linkedin_url)
    if handle_match:
        handle = handle_match.group(1).lower()
    else:
        handle = re.sub(r"[^a-z0-9]+", "-", linkedin_url.lower()).strip("-")[:32] or "profile"
    digest = hashlib.sha1(f"{linkedin_url}:{time.time()}".encode()).hexdigest()[:6]
    return f"{handle}-{digest}"


def render_html(*, title: str, subtitle: str, linkedin_url: str, body_html: str, date: str) -> str:
    return BRIEF_TEMPLATE.format(
        title=escape(title),
        subtitle=escape(subtitle),
        linkedin_url=escape(linkedin_url, quote=True),
        body=body_html,  # body is trusted (model output, sanitized upstream)
        date=escape(date),
    )


def save_brief(briefs_dir: Path, slug: str, html: str) -> Path:
    briefs_dir.mkdir(parents=True, exist_ok=True)
    path = briefs_dir / f"{slug}.html"
    path.write_text(html, encoding="utf-8")
    return path


def load_brief(briefs_dir: Path, slug: str) -> str | None:
    if not re.fullmatch(r"[a-z0-9_\-]{3,80}", slug):
        return None
    path = briefs_dir / f"{slug}.html"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")
