"""Render a ReasonTree search as a navigable, self-contained HTML artifact.

The input is a domain-neutral tree spec (plain dict / JSON), so any adapter
can emit one. Nothing here knows about chess; ``chess_artifact.py`` is one
producer. The output HTML has zero external dependencies (inline CSS/JS only),
renders in light and dark themes, and keeps every branch inspectable through
native ``<details>`` elements, so the tree is keyboard-navigable by default.

Spec shape (all string fields are plain text; the renderer escapes them):

    {
      "title": "...",
      "task": "one-line task statement",
      "state": "pre-rendered current state (monospace block)",
      "budget": {"depth": 4, "max_nodes": 300000, "timeout_s": 12.0,
                 "nodes_used": 52310, "wall_seconds": 4.37, "completed": true},
      "selected_action": "Bxd5",
      "nodes": [
        {"action": "Bxd5", "score": 880, "score_label": "+8.8",
         "verdict": "selected" | "survives" | "refuted" | "pruned",
         "role": "candidate" | "reply" | "continuation",
         "note": "short branch thought",
         "line": ["Bxd5", "exd5", "Rxe7"],
         "children": [ ...same shape... ]},
        ...
      ],
      "raw_trace": {                      # optional comparison pane
        "label": "raw haiku, same prompt",
        "status": "timeout" | "budget_exhausted" | "completed",
        "wall_seconds": 600.0,
        "streamed_chars": 18342,
        "excerpts": [{"t": 3.1, "text": "..."}, ...],
        "unfinished": true
      }
    }
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


_CSS = """
:root{
  --paper:#FBFBF8;--ink:#1F2421;--ink-2:#5A625D;--ink-3:#8B938D;
  --line:#E3E4DD;--card:#FFFFFF;--card-2:#F3F4EE;
  --rt:#178A52;--rt-soft:#E2F1E8;--base:#3667D6;--base-soft:#E6ECF9;
  --crit:#B4432E;--crit-soft:#F7E7E2;
}
@media (prefers-color-scheme: dark){:root{
  --paper:#15181A;--ink:#E8EAE6;--ink-2:#A9B0AA;--ink-3:#767D77;
  --line:#2A2F30;--card:#1C2022;--card-2:#22272A;
  --rt:#1FA268;--rt-soft:#173328;--base:#5484F0;--base-soft:#1B2740;
  --crit:#E06A50;--crit-soft:#3A231D;}}
:root[data-theme="dark"]{
  --paper:#15181A;--ink:#E8EAE6;--ink-2:#A9B0AA;--ink-3:#767D77;
  --line:#2A2F30;--card:#1C2022;--card-2:#22272A;
  --rt:#1FA268;--rt-soft:#173328;--base:#5484F0;--base-soft:#1B2740;
  --crit:#E06A50;--crit-soft:#3A231D;}
:root[data-theme="light"]{
  --paper:#FBFBF8;--ink:#1F2421;--ink-2:#5A625D;--ink-3:#8B938D;
  --line:#E3E4DD;--card:#FFFFFF;--card-2:#F3F4EE;
  --rt:#178A52;--rt-soft:#E2F1E8;--base:#3667D6;--base-soft:#E6ECF9;
  --crit:#B4432E;--crit-soft:#F7E7E2;}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1060px;margin:0 auto;padding:40px 22px 80px}
.serif{font-family:"Iowan Old Style",Palatino,Georgia,serif}
.mono{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;font-variant-numeric:tabular-nums}
.eyebrow{font-size:11.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--ink-3);font-weight:650}
h1{font-size:clamp(26px,4.5vw,38px);line-height:1.12;margin:8px 0 8px;text-wrap:balance;font-weight:600}
.task{color:var(--ink-2);max-width:70ch;margin:0 0 20px;font-size:16px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;align-items:start}
@media (max-width:880px){.grid{grid-template-columns:1fr}}
.pane{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;
  box-shadow:0 1px 2px rgba(0,0,0,.05),0 4px 16px rgba(0,0,0,.05)}
.pane-h{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid var(--line)}
.pane-h .t{font-weight:650;font-size:14px}
.pane-h .badge{margin-left:auto}
.pane-b{padding:14px 16px}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:650;
  padding:2px 9px;border-radius:99px;white-space:nowrap}
.chip .dot{width:6px;height:6px;border-radius:99px;background:currentColor;flex:none}
.chip.ok{background:var(--rt-soft);color:var(--rt)}
.chip.bad{background:var(--crit-soft);color:var(--crit)}
.chip.info{background:var(--base-soft);color:var(--base)}
.chip.mut{background:var(--card-2);color:var(--ink-2)}
.state{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:12.5px;line-height:1.5;
  background:var(--card-2);border:1px solid var(--line);border-radius:8px;padding:10px 12px;
  overflow-x:auto;white-space:pre;margin:0 0 14px}
.budget{display:flex;flex-wrap:wrap;gap:7px;margin:0 0 14px}
/* raw stream pane */
.stream{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:12.5px;line-height:1.62;
  color:var(--ink-2);max-height:560px;overflow-y:auto;padding-right:6px}
.stream .tick{display:block;font-size:10.5px;color:var(--base);letter-spacing:.08em;
  margin:14px 0 3px;font-weight:700}
.stream .tick:first-child{margin-top:0}
.stream p{margin:0 0 8px;white-space:pre-wrap;word-break:break-word}
.ellipsis{color:var(--crit);font-weight:700;letter-spacing:.18em;font-size:16px}
@media (prefers-reduced-motion: no-preference){
  .ellipsis{animation:blink 1.4s steps(1) infinite}
  @keyframes blink{50%{opacity:.25}}}
.cut{border:0;border-top:2px dashed var(--crit);margin:10px 0 8px;position:relative}
.cutlabel{font-size:11px;color:var(--crit);font-weight:700;letter-spacing:.08em;text-transform:uppercase}
/* tree */
.tree{list-style:none;margin:0;padding:0}
.tree ul{list-style:none;margin:0;padding-left:20px;border-left:2px solid var(--line)}
.tree li{margin:0 0 8px}
details.node>summary{list-style:none;cursor:pointer;display:block;border:1px solid var(--line);
  border-radius:9px;background:var(--card);padding:8px 12px;position:relative}
details.node>summary::-webkit-details-marker{display:none}
details.node>summary:focus-visible{outline:2px solid var(--base);outline-offset:2px}
details.node[open]>summary{border-bottom-left-radius:0;border-bottom-right-radius:0}
details.node>.kids{border:1px solid var(--line);border-top:0;border-radius:0 0 9px 9px;
  padding:10px 12px 6px;background:var(--card-2)}
.n-top{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.n-act{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-weight:700;font-size:13.5px}
.n-role{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);font-weight:700}
.n-score{margin-left:auto;display:flex;align-items:center;gap:8px}
.sbar{width:74px;height:7px;border-radius:4px;background:var(--card-2);position:relative;overflow:hidden;
  border:1px solid var(--line)}
.sbar i{position:absolute;inset:0 auto 0 0;border-radius:3px}
.n-sval{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:12px;font-weight:650;min-width:44px;text-align:right}
.n-note{font-size:13px;color:var(--ink-2);margin:5px 0 0;max-width:64ch}
.n-line{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:11.5px;color:var(--ink-3);margin-top:4px}
.n-line b{color:var(--ink-2)}
.caret{display:inline-block;transition:transform .15s ease;color:var(--ink-3);font-size:11px}
details[open]>summary .caret{transform:rotate(90deg)}
.node.v-selected>summary{border-color:var(--rt);box-shadow:inset 3px 0 0 var(--rt)}
.node.v-refuted>summary{box-shadow:inset 3px 0 0 var(--crit)}
.legendrow{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.controls{display:flex;gap:8px;margin:0 0 12px}
.controls button{font:inherit;font-size:12.5px;font-weight:600;color:var(--ink-2);
  background:var(--card-2);border:1px solid var(--line);border-radius:7px;padding:4px 12px;cursor:pointer}
.controls button:focus-visible{outline:2px solid var(--base);outline-offset:1px}
.verdictline{margin-top:16px;padding:12px 14px;border-radius:9px;background:var(--rt-soft);
  color:var(--ink);font-size:14px}
.verdictline b{color:var(--rt)}
.foot{margin-top:34px;font-size:12px;color:var(--ink-3);line-height:1.6}
"""

_JS = """
document.querySelectorAll('[data-expand]').forEach(function(btn){
  btn.addEventListener('click',function(){
    var open = btn.getAttribute('data-expand')==='1';
    document.querySelectorAll('details.node').forEach(function(d){d.open=open;});
  });
});
"""

_VERDICT_CHIP = {
    "selected": ("ok", "selected"),
    "survives": ("info", "survives"),
    "refuted": ("bad", "refuted"),
    "pruned": ("mut", "pruned"),
}


def _score_bar(node: dict[str, Any], max_abs: float) -> str:
    score = node.get("score")
    if score is None:
        return ""
    frac = min(1.0, abs(float(score)) / max_abs) if max_abs else 0.0
    color = "var(--rt)" if float(score) >= 0 else "var(--crit)"
    label = node.get("score_label", score)
    return (
        f'<span class="n-score"><span class="sbar"><i style="width:{frac * 100:.0f}%;'
        f'background:{color}"></i></span><span class="n-sval">{_esc(label)}</span></span>'
    )


def _render_node(node: dict[str, Any], max_abs: float, depth: int) -> str:
    verdict = str(node.get("verdict", ""))
    chip_kind, chip_text = _VERDICT_CHIP.get(verdict, ("", ""))
    chip = f'<span class="chip {chip_kind}"><span class="dot"></span>{_esc(chip_text)}</span>' if chip_kind else ""
    role = node.get("role")
    role_html = f'<span class="n-role">{_esc(role)}</span>' if role else ""
    note = node.get("note")
    note_html = f'<div class="n-note">{_esc(note)}</div>' if note else ""
    line = node.get("line") or []
    line_html = (
        f'<div class="n-line">line: <b>{_esc(" ".join(str(m) for m in line))}</b></div>' if line else ""
    )
    children = node.get("children") or []
    kids_html = ""
    caret = ""
    if children:
        caret = '<span class="caret">&#9656;</span> '
        inner = "".join(f"<li>{_render_node(c, max_abs, depth + 1)}</li>" for c in children)
        kids_html = f'<div class="kids"><ul class="tree">{inner}</ul></div>'
    open_attr = " open" if verdict == "selected" and depth == 0 else ""
    classes = f"node v-{verdict}" if verdict else "node"
    summary = (
        f'<summary><div class="n-top">{caret}<span class="n-act">{_esc(node.get("action", ""))}</span>'
        f"{role_html}{chip}{_score_bar(node, max_abs)}</div>{note_html}{line_html}</summary>"
    )
    if not children:
        # childless nodes render as non-collapsible cards for cleaner keyboard flow
        return f'<details class="{classes}"{open_attr}>{summary}</details>'
    return f'<details class="{classes}"{open_attr}>{summary}{kids_html}</details>'


def _collect_scores(nodes: list[dict[str, Any]]) -> list[float]:
    scores: list[float] = []
    for node in nodes:
        if node.get("score") is not None:
            scores.append(abs(float(node["score"])))
        scores.extend(_collect_scores(node.get("children") or []))
    return scores


def _render_raw_pane(raw: dict[str, Any]) -> str:
    final = raw.get("final") or {}
    status = str(raw.get("status", ""))
    if final.get("predicted") and not final.get("correct"):
        status_chip = (
            f'<span class="chip bad badge"><span class="dot"></span>committed to the wrong move '
            f"at {_esc(final.get('wall_seconds', raw.get('wall_seconds', '?')))}s</span>"
        )
    elif status != "completed":
        status_chip = (
            f'<span class="chip bad badge"><span class="dot"></span>{_esc(status)} '
            f"at {_esc(raw.get('wall_seconds', '?'))}s</span>"
        )
    else:
        status_chip = '<span class="chip ok badge"><span class="dot"></span>completed</span>'

    # merge excerpts and time markers into one timeline, sorted by t
    items: list[tuple[float, str]] = []
    for ex in raw.get("excerpts", []):
        t = float(ex.get("t", 0))
        items.append(
            (t, f'<span class="tick">t = {_esc(ex.get("t", "?"))}s</span><p>{_esc(ex.get("text", ""))} '
                '<span class="ellipsis">&hellip;</span></p>')
        )
    for marker in raw.get("markers", []):
        t = float(marker.get("t", 0))
        items.append(
            (t, f'<hr class="cut"><span class="cutlabel">t = {_esc(marker.get("t", "?"))}s &mdash; '
                f"{_esc(marker.get('label', ''))}</span>")
        )
    items.sort(key=lambda pair: pair[0])
    parts = [chunk for _, chunk in items]

    tail = ""
    if final.get("predicted"):
        verdict = "correct" if final.get("correct") else "wrong"
        expected = f" (expected {_esc(final['expected'])})" if final.get("expected") and not final.get("correct") else ""
        note = f" &mdash; {_esc(final['note'])}" if final.get("note") else ""
        tail = (
            f'<hr class="cut"><span class="cutlabel">t = {_esc(final.get("wall_seconds", "?"))}s &mdash; finally '
            f"commits to {_esc(final['predicted'])} — {verdict}{expected}{note}</span>"
        )
    elif raw.get("unfinished"):
        tail = (
            '<hr class="cut"><span class="cutlabel">still generating when the budget ended — '
            'no move was ever committed</span> <span class="ellipsis">&hellip;</span>'
        )
    meta_chips = [
        f'<span class="chip mut">wall {_esc(raw.get("wall_seconds", "?"))}s</span>',
        f'<span class="chip mut">{_esc(raw.get("streamed_chars", "?"))} chars streamed</span>',
    ]
    if raw.get("output_tokens"):
        meta_chips.append(f'<span class="chip mut">{_esc(raw["output_tokens"])} output tokens</span>')
    if raw.get("cost_usd") is not None:
        meta_chips.append(f'<span class="chip mut">${_esc(raw["cost_usd"])}</span>')
    meta = f'<div class="budget">{"".join(meta_chips)}</div>'
    return (
        f'<section class="pane"><div class="pane-h"><span class="t">{_esc(raw.get("label", "raw model"))}</span>'
        f'{status_chip}</div><div class="pane-b">{meta}<div class="stream">{"".join(parts)}{tail}</div></div></section>'
    )


def render_body(spec: dict[str, Any]) -> str:
    nodes = spec.get("nodes") or []
    scores = _collect_scores(nodes)
    max_abs = max(scores) if scores else 1.0
    budget = spec.get("budget") or {}
    budget_chips = "".join(
        f'<span class="chip mut">{_esc(k.replace("_", " "))}: {_esc(v)}</span>' for k, v in budget.items()
    )
    state = spec.get("state")
    state_html = f'<pre class="state">{_esc(state)}</pre>' if state else ""
    tree_items = "".join(f"<li>{_render_node(n, max_abs, 0)}</li>" for n in nodes)
    selected = spec.get("selected_action")
    verdict_html = (
        f'<div class="verdictline">Controller selection: <b>{_esc(selected)}</b> &mdash; the branch that '
        f"survives the opponent&rsquo;s strongest reply within the budget.</div>"
        if selected
        else ""
    )
    raw = spec.get("raw_trace")
    tree_pane = (
        '<section class="pane"><div class="pane-h"><span class="t">ReasonTree bounded search</span>'
        '<span class="chip ok badge"><span class="dot"></span>every branch inspectable</span></div>'
        f'<div class="pane-b">{state_html}<div class="budget">{budget_chips}</div>'
        '<div class="controls"><button type="button" data-expand="1">Expand all</button>'
        '<button type="button" data-expand="0">Collapse all</button></div>'
        f'<ul class="tree">{tree_items}</ul>{verdict_html}</div></section>'
    )
    panes = (_render_raw_pane(raw) + tree_pane) if raw else tree_pane
    grid_class = "grid" if raw else ""
    return (
        f'<div class="wrap"><header><div class="eyebrow">{_esc(spec.get("eyebrow", "ReasonTree artifact"))}</div>'
        f'<h1 class="serif">{_esc(spec.get("title", "ReasonTree search"))}</h1>'
        f'<p class="task">{_esc(spec.get("task", ""))}</p></header>'
        f'<div class="{grid_class}">{panes}</div>'
        f'<footer class="foot">{_esc(spec.get("footnote", ""))}</footer></div>'
    )


def render_page(spec: dict[str, Any], *, fragment: bool = False) -> str:
    body = render_body(spec)
    core = f"<style>{_CSS}</style>\n{body}\n<script>{_JS}</script>"
    if fragment:
        return f"<title>{_esc(spec.get('title', 'ReasonTree'))}</title>\n{core}"
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{_esc(spec.get('title', 'ReasonTree'))}</title></head><body>{core}</body></html>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a ReasonTree spec JSON to a self-contained HTML artifact.")
    parser.add_argument("--spec", type=Path, required=True, help="tree spec JSON file")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fragment", action="store_true", help="emit a body fragment instead of a full page")
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    args.output.write_text(render_page(spec, fragment=args.fragment), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
