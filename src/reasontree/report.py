from __future__ import annotations

import os
from html import escape
from pathlib import Path

from .core import SearchResult


def write_html_report(results: list[SearchResult], path: Path) -> None:
    cards = "\n".join(_card(result, path) for result in results)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ReasonTree Demo</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #111827; background: #f8fafc; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 40px 20px 56px; }}
    h1 {{ margin: 0 0 8px; font-size: 36px; letter-spacing: 0; }}
    h2 {{ margin-top: 32px; }}
    p {{ line-height: 1.55; }}
    code {{ background: #eef2f7; border-radius: 4px; padding: 1px 4px; }}
    .summary {{ color: #475569; max-width: 760px; }}
    .boards {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; margin: 20px 0; }}
    .board {{ border: 1px solid #e5e7eb; border-radius: 6px; overflow: hidden; background: white; }}
    .board img {{ display: block; width: 100%; height: auto; }}
    .board span {{ display: block; padding: 8px; font-size: 13px; color: #334155; border-top: 1px solid #e5e7eb; }}
    .trace {{ background: white; border: 1px solid #e5e7eb; border-radius: 6px; padding: 18px 22px; }}
    .trace li {{ margin: 8px 0; line-height: 1.45; }}
    @media (max-width: 760px) {{ .boards {{ grid-template-columns: 1fr 1fr; }} }}
  </style>
</head>
<body>
  <main>
    <h1>ReasonTree</h1>
    <p class="summary">A small state-action tree for making Claude compare possible paths before committing to an answer.</p>
    {cards}
  </main>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def _card(result: SearchResult, path: Path) -> str:
    root = Path(__file__).resolve().parents[2]
    trace = "\n".join(f"<li>{escape(line)}</li>" for line in result.trace)
    return f"""<section>
  <h2>Chess Demo</h2>
  <p><code>{escape(result.problem)}</code>: ReasonTree selects <strong>{escape(result.best_action)}</strong>.</p>
  <div class="boards">
    <div class="board"><img src="{_rel(path, root / "assets/chess/reasontree-ch-01-start.svg")}" alt="Start position"><span>Start position</span></div>
    <div class="board"><img src="{_rel(path, root / "assets/chess/reasontree-ch-01-step-1-bxg5.svg")}" alt="Bxg5+"><span>1. Bxg5+</span></div>
    <div class="board"><img src="{_rel(path, root / "assets/chess/reasontree-ch-01-step-2-kxg5.svg")}" alt="Kxg5"><span>1... Kxg5</span></div>
    <div class="board"><img src="{_rel(path, root / "assets/chess/reasontree-ch-01-step-3-qf4-mate.svg")}" alt="Qf4 mate"><span>2. Qf4#</span></div>
  </div>
  <ol class="trace">{trace}</ol>
</section>"""


def _rel(path: Path, target: Path) -> str:
    return escape(os.path.relpath(target, start=path.parent))

