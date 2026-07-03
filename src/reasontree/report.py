from __future__ import annotations

import json
import os
from html import escape
from pathlib import Path

from .core import SearchResult


def write_html_report(results: list[SearchResult], path: Path) -> None:
    evidence = _evidence_section(path)
    cards = "\n".join(_card(result) for result in results)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ReasonTree Demo Report</title>
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{ startOnLoad: true, theme: 'base' }});
  </script>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f7f8fa; color: #111827; }}
    header {{ padding: 40px 48px 24px; background: #1f2937; color: white; }}
    h1 {{ margin: 0 0 8px; font-size: 34px; letter-spacing: 0; }}
    header p {{ max-width: 820px; margin: 0; color: #cbd5e1; font-size: 17px; line-height: 1.5; }}
    main {{ padding: 28px 48px 56px; display: grid; gap: 24px; }}
    section {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 24px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05); }}
    h2 {{ margin: 0 0 16px; font-size: 22px; }}
    p {{ line-height: 1.55; }}
    a {{ color: #0f766e; }}
    code {{ background: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 4px; padding: 1px 4px; }}
    .evidence-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin: 18px 0; }}
    .evidence-card {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; background: #fbfcfd; }}
    .evidence-card h3 {{ margin: 0 0 12px; font-size: 17px; }}
    .status {{ display: inline-block; border-radius: 999px; padding: 4px 9px; font-size: 12px; font-weight: 700; margin-bottom: 12px; }}
    .status.bad {{ background: #fee2e2; color: #991b1b; }}
    .status.good {{ background: #dcfce7; color: #166534; }}
    .facts {{ margin: 0; padding-left: 18px; line-height: 1.6; }}
    .note {{ margin: 14px 0 0; color: #475569; font-size: 14px; }}
    .boards {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; margin-top: 16px; }}
    .board {{ border: 1px solid #e5e7eb; border-radius: 6px; overflow: hidden; background: white; }}
    .board img {{ display: block; width: 100%; height: auto; }}
    .board span {{ display: block; padding: 8px; font-size: 13px; color: #334155; border-top: 1px solid #e5e7eb; }}
    .verdict {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 18px; }}
    .metric {{ border: 1px solid #e5e7eb; border-radius: 6px; padding: 12px; background: #f9fafb; }}
    .label {{ display: block; color: #64748b; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; margin-bottom: 5px; }}
    .value {{ font-size: 17px; font-weight: 650; }}
    .trace {{ margin: 0; padding-left: 20px; line-height: 1.55; }}
    .mermaid {{ margin-top: 18px; padding: 12px; border: 1px solid #e5e7eb; border-radius: 6px; background: #ffffff; overflow-x: auto; }}
    @media (max-width: 760px) {{ header, main {{ padding-left: 18px; padding-right: 18px; }} .verdict, .evidence-grid, .boards {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <header>
    <h1>ReasonTree</h1>
    <p>Search-time reasoning for LLMs: separate facts from assumptions, branch into actions, simulate next states, score paths, and synthesize an auditable answer instead of one brittle reply.</p>
  </header>
  <main>
    {evidence}
    {cards}
  </main>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def _evidence_section(path: Path) -> str:
    root = Path(__file__).resolve().parents[2]
    direct_file = root / "evals/raw_model_outputs/chess_reasontree_ch_01_direct_sonnet5_medium_20260702.json.timeout.txt"
    direct_meta = root / "evals/raw_model_outputs/chess_reasontree_ch_01_direct_sonnet5_medium_20260702.metadata.json"
    opus_file = root / "evals/raw_model_outputs/chess_reasontree_ch_01_direct_structured_opus48_medium_safemode_20260702.json.timeout.txt"
    opus_meta = root / "evals/raw_model_outputs/chess_reasontree_ch_01_direct_structured_opus48_medium_safemode_20260702.metadata.json"
    skill_file = root / "evals/raw_model_outputs/chess_reasontree_ch_01_skill_tools_fastpath_sonnet5_medium_20260702.json"
    direct_prompt = root / "evals/prompts/chess_mate2_direct.md"
    skill_prompt = root / "evals/prompts/chess_mate2_reasontree_tool.md"
    verifier = root / "scripts/chess_mate_search.py"
    skill = _read_skill_result(skill_file)

    return f"""<section>
  <h2>Direct Sonnet 5 vs ReasonTree</h2>
  <p>Same chess position, local Claude Code harness, effort <code>medium</code>. Direct one-shot runs are tracked as completion evidence, not as proof that a model can never solve the puzzle.</p>
  <div class="evidence-grid">
    <div class="evidence-card">
      <h3>Direct one-shot ask</h3>
      <div class="status bad">Did not complete</div>
      <ul class="facts">
        <li>Prompt: <a href="{_rel(path, direct_prompt)}">chess_mate2_direct.md</a></li>
        <li>Sonnet 5: timeout after 75 seconds, <a href="{_rel(path, direct_file)}">raw file</a>, <a href="{_rel(path, direct_meta)}">metadata</a></li>
        <li>Opus 4.8 safe mode: timeout after 90 seconds, <a href="{_rel(path, opus_file)}">raw file</a>, <a href="{_rel(path, opus_meta)}">metadata</a></li>
      </ul>
    </div>
    <div class="evidence-card">
      <h3><code>/reasontree</code> with tools</h3>
      <div class="status good">Solved with verified path</div>
      <ul class="facts">
        <li>Prompt: <a href="{_rel(path, skill_prompt)}">chess_mate2_reasontree_tool.md</a></li>
        <li>Result: <code>{escape(skill["line"])}</code></li>
        <li>Runtime: {escape(skill["duration"])}</li>
        <li>Raw evidence: <a href="{_rel(path, skill_file)}">structured JSON output</a></li>
      </ul>
    </div>
  </div>
  <p class="note">The successful run uses the ReasonTree skill with tools enabled and the repo-local verifier <a href="{_rel(path, verifier)}">chess_mate_search.py</a> as the scorer. Pure text skill runs are kept in <code>evals/raw_model_outputs/</code> as timeout evidence; the public demo should not claim a magic prompt solved the puzzle.</p>
  <div class="boards">
    <div class="board"><img src="{_rel(path, root / "assets/chess/reasontree-ch-01-start.svg")}" alt="Start position"><span>Start position</span></div>
    <div class="board"><img src="{_rel(path, root / "assets/chess/reasontree-ch-01-step-1-bxg5.svg")}" alt="Bxg5+"><span>1. Bxg5+</span></div>
    <div class="board"><img src="{_rel(path, root / "assets/chess/reasontree-ch-01-step-2-kxg5.svg")}" alt="Kxg5"><span>1... Kxg5</span></div>
    <div class="board"><img src="{_rel(path, root / "assets/chess/reasontree-ch-01-step-3-qf4-mate.svg")}" alt="Qf4 mate"><span>2. Qf4#</span></div>
  </div>
</section>"""


def _read_skill_result(path: Path) -> dict[str, str]:
    if not path.exists():
        return {"line": "missing run", "duration": "not available"}
    data = json.loads(path.read_text(encoding="utf-8"))
    structured = data.get("structured_output", {})
    line = " ".join(structured.get("principal_variation", [])) or structured.get("move", "missing move")
    duration = data.get("duration_ms")
    duration_text = f"{duration / 1000:.1f}s" if isinstance(duration, int) else "not available"
    return {"line": line, "duration": duration_text}


def _rel(path: Path, target: Path) -> str:
    return escape(os.path.relpath(target, start=path.parent))


def _card(result: SearchResult) -> str:
    trace = "\n".join(f"<li>{escape(line)}</li>" for line in result.trace)
    synthesis = _synthesis(result)
    return f"""<section>
  <h2>{escape(result.problem)}</h2>
  <div class="verdict">
    <div class="metric"><span class="label">Direct baseline</span><span class="value">{escape(result.direct_baseline)}</span></div>
    <div class="metric"><span class="label">Expected</span><span class="value">{escape(result.expected)}</span></div>
    <div class="metric"><span class="label">ReasonTree</span><span class="value">{escape(result.best_action)} ({result.best_reward:.2f})</span></div>
  </div>
  <ol class="trace">{trace}</ol>
  {synthesis}
  <pre class="mermaid">{escape(result.mermaid)}</pre>
</section>"""


def _synthesis(result: SearchResult) -> str:
    synthesis = result.tree_synthesis
    if not synthesis:
        return ""
    items: list[str] = []
    for label, key in [
        ("Facts used", "selected_path_facts"),
        ("Assumptions", "selected_path_assumptions"),
        ("Beliefs tested", "selected_path_beliefs_tested"),
        ("Takeaway", "robust_takeaway"),
    ]:
        value = synthesis.get(key)
        if isinstance(value, list) and value:
            items.append(f"<li><strong>{escape(label)}:</strong> {escape(', '.join(str(item) for item in value))}</li>")
        elif isinstance(value, str) and value:
            items.append(f"<li><strong>{escape(label)}:</strong> {escape(value)}</li>")
    if not items:
        return ""
    return f"""<div class="evidence-card">
    <h3>Tree synthesis</h3>
    <ul class="facts">{''.join(items)}</ul>
  </div>"""
