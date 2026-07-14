"""Render a ReasonTree search as a navigable, self-contained HTML artifact.

The input is a domain-neutral tree spec (plain dict / JSON), so any adapter
can emit one. Nothing here knows about chess; ``chess_artifact.py`` is one
producer. The output HTML has zero external dependencies (inline CSS/JS only),
renders in light and dark themes, and keeps every branch inspectable.

Two layouts:

- ``"layout": "horizontal"`` (default) — a left-to-right tree with drawn
  connector lines. Line weight and color follow the branch verdict (the
  selected path is bold, refuted branches thin), and every node with children
  toggles open/closed on click or Enter/Space.
- ``"layout": "vertical"`` — nested ``<details>`` cards, useful for deep
  narrow trees.

Spec shape (all string fields are plain text; the renderer escapes them —
except ``board_svg``, which is inserted verbatim and must come from a trusted
generator such as ``chess.svg.board``):

    {
      "title": "...",
      "task": "one-line task statement",
      "layout": "horizontal",
      "board_svg": "<svg .../>",           # optional rendered state diagram
      "board_caption": "White to move · rated 1809",
      "state": "monospace state block",     # optional textual state
      "budget": {"depth": 4, "wall_seconds": 4.3, ...},
      "selected_action": "Qxd5",
      "nodes": [
        {"action": "Qxd5", "score": 164, "score_label": "+1.6",
         "verdict": "selected" | "survives" | "refuted" | "pruned",
         "role": "candidate" | "reply" | "continuation",
         "note": "short branch thought",
         "line": ["Qxd5", "exd5", "Rxe7"],
         "children": [ ...same shape... ]},
      ],
      "raw_trace": {                        # optional comparison pane
        "label": "raw haiku — same prompt",
        "status": "completed" | "timeout" | "budget_exhausted",
        "wall_seconds": 127.4, "streamed_chars": 17594,
        "output_tokens": 12974, "cost_usd": 0.0692,
        "excerpts": [{"t": 1.9, "text": "..."}],
        "markers": [{"t": 30, "label": "operational cap"}],
        "final": {"predicted": "c1c8", "expected": "b3d5",
                  "correct": false, "wall_seconds": 127.4, "note": "..."},
        "unfinished": false
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
.wrap{max-width:1160px;margin:0 auto;padding:40px 22px 80px}
.serif{font-family:"Iowan Old Style",Palatino,Georgia,serif}
.mono{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;font-variant-numeric:tabular-nums}
.eyebrow{font-size:11.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--ink-3);font-weight:650}
h1{font-size:clamp(26px,4.5vw,38px);line-height:1.12;margin:8px 0 8px;text-wrap:balance;font-weight:600}
.task{color:var(--ink-2);max-width:66ch;margin:0;font-size:16px}
.hero{display:flex;gap:30px;align-items:flex-start;flex-wrap:wrap;margin-bottom:26px}
.hero .intro{flex:1 1 420px;min-width:300px}
.board{flex:0 0 auto}
.board svg{display:block;max-width:100%;height:auto;border-radius:10px;
  box-shadow:0 1px 2px rgba(0,0,0,.08),0 6px 20px rgba(0,0,0,.08)}
.board figcaption{font-size:12.5px;color:var(--ink-2);text-align:center;margin-top:8px}
.stack{display:grid;gap:20px}
.pane{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;
  box-shadow:0 1px 2px rgba(0,0,0,.05),0 4px 16px rgba(0,0,0,.05)}
.pane-h{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid var(--line);flex-wrap:wrap}
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
  color:var(--ink-2);max-height:430px;overflow-y:auto;padding-right:6px;
  column-width:430px;column-gap:34px;column-rule:1px solid var(--line)}
.stream>div{break-inside:avoid;margin-bottom:10px}
.stream .tick{display:block;font-size:10.5px;color:var(--base);letter-spacing:.08em;
  margin:0 0 3px;font-weight:700}
.stream p{margin:0;white-space:pre-wrap;word-break:break-word}
.ellipsis{color:var(--crit);font-weight:700;letter-spacing:.18em;font-size:16px}
@media (prefers-reduced-motion: no-preference){
  .ellipsis{animation:blink 1.4s steps(1) infinite}
  @keyframes blink{50%{opacity:.25}}}
.cut{border:0;border-top:2px dashed var(--crit);margin:4px 0 6px}
.cutlabel{font-size:11px;color:var(--crit);font-weight:700;letter-spacing:.08em;text-transform:uppercase}
/* ---- horizontal tree ---- */
.htree-scroll{overflow-x:auto;padding:8px 2px 14px}
.htree{display:inline-flex;flex-direction:column;gap:14px;min-width:100%}
.brow{display:flex;align-items:center}
.ncard{background:var(--card);border:1.5px solid var(--line);border-radius:10px;padding:9px 13px;
  min-width:210px;max-width:290px;flex:none;position:relative}
.ncard.toggle{cursor:pointer}
.ncard.toggle:focus-visible{outline:2px solid var(--base);outline-offset:2px}
.ncard.v-selected{border-color:var(--rt);border-width:2px;box-shadow:0 2px 10px rgba(23,138,82,.18)}
.ncard.v-refuted{border-color:color-mix(in srgb, var(--crit) 55%, var(--line))}
.n-top{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.n-act{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-weight:700;font-size:14px}
.n-role{font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);font-weight:700}
.n-score{margin-left:auto;display:flex;align-items:center;gap:7px}
.sbar{width:56px;height:6px;border-radius:4px;background:var(--card-2);position:relative;overflow:hidden;
  border:1px solid var(--line)}
.sbar i{position:absolute;inset:0 auto 0 0;border-radius:3px}
.n-sval{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:12px;font-weight:650}
.n-note{font-size:12px;color:var(--ink-2);margin:4px 0 0;line-height:1.45}
.n-line{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:10.5px;color:var(--ink-3);margin-top:4px}
.n-line b{color:var(--ink-2);font-weight:650}
.caret{position:absolute;right:-9px;top:50%;transform:translateY(-50%);width:18px;height:18px;
  border-radius:99px;background:var(--card);border:1.5px solid var(--line);color:var(--ink-2);
  font-size:10px;line-height:15px;text-align:center;transition:transform .15s ease;z-index:1}
.brow.open>.ncard>.caret{transform:translateY(-50%) rotate(90deg)}
.ncard.root{background:var(--card-2);min-width:150px;max-width:190px;border-style:solid;
  border-color:var(--ink-3)}
.ncard.root .n-act{font-size:12.5px}
.stub{width:30px;height:0;border-top:3px solid var(--ink-3);opacity:.55;flex:none;align-self:center}
.brow.sel>.stub{border-top:4px solid var(--rt);opacity:1}
.brow.ref>.stub{border-top:2px solid var(--crit);opacity:.7}
ul.kids{list-style:none;display:flex;flex-direction:column;gap:12px;margin:0;padding:6px 0}
ul.kids>li{position:relative;padding-left:30px;display:flex}
ul.kids>li::before{content:"";position:absolute;left:0;top:50%;width:30px;border-top:3px solid var(--ink-3);opacity:.55}
ul.kids>li::after{content:"";position:absolute;left:-1.5px;top:0;bottom:0;border-left:3px solid var(--ink-3);opacity:.55}
ul.kids>li:first-child::after{top:50%}
ul.kids>li:last-child::after{bottom:50%}
ul.kids>li:first-child:last-child::after{display:none}
ul.kids>li.sel::before{border-top:4px solid var(--rt);top:calc(50% - 1px);opacity:1}
ul.kids>li.ref::before{border-top:2px solid var(--crit);opacity:.7}
.brow[data-collapsed="1"]>.stub,.brow[data-collapsed="1"]>ul.kids{display:none}
/* ---- vertical fallback tree ---- */
.vtree{list-style:none;margin:0;padding:0}
.vtree ul{list-style:none;margin:0;padding-left:20px;border-left:2px solid var(--line)}
.vtree li{margin:0 0 8px}
details.node>summary{list-style:none;cursor:pointer;display:block;border:1px solid var(--line);
  border-radius:9px;background:var(--card);padding:8px 12px}
details.node>summary::-webkit-details-marker{display:none}
details.node>summary:focus-visible{outline:2px solid var(--base);outline-offset:2px}
details.node>.dkids{border:1px solid var(--line);border-top:0;border-radius:0 0 9px 9px;
  padding:10px 12px 6px;background:var(--card-2)}
.node.v-selected>summary{border-color:var(--rt);box-shadow:inset 3px 0 0 var(--rt)}
.node.v-refuted>summary{box-shadow:inset 3px 0 0 var(--crit)}
/* shared */
.controls{display:flex;gap:8px;margin:0 0 12px}
.controls button{font:inherit;font-size:12.5px;font-weight:600;color:var(--ink-2);
  background:var(--card-2);border:1px solid var(--line);border-radius:7px;padding:4px 12px;cursor:pointer}
.controls button:focus-visible{outline:2px solid var(--base);outline-offset:1px}
.verdictline{margin-top:14px;padding:12px 14px;border-radius:9px;background:var(--rt-soft);
  color:var(--ink);font-size:14px}
.verdictline b{color:var(--rt)}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--ink-2);margin-top:12px}
.legend .li{display:flex;align-items:center;gap:7px}
.legend .sw{width:22px;flex:none}
.legend .sw.selline{border-top:4px solid var(--rt)}
.legend .sw.survline{border-top:2.5px solid var(--line)}
.legend .sw.refline{border-top:2px solid color-mix(in srgb, var(--crit) 60%, var(--line))}
.foot{margin-top:30px;font-size:12px;color:var(--ink-3);line-height:1.6}
"""

_JS = """
function setOpen(row, open){
  row.setAttribute('data-collapsed', open ? '0' : '1');
  row.classList.toggle('open', open);
  var card = row.querySelector(':scope > .ncard');
  if (card) card.setAttribute('aria-expanded', open ? 'true' : 'false');
}
document.querySelectorAll('.brow').forEach(function(row){
  var card = row.querySelector(':scope > .ncard.toggle');
  if(!card) return;
  function flip(){ setOpen(row, row.getAttribute('data-collapsed') === '1'); }
  card.addEventListener('click', flip);
  card.addEventListener('keydown', function(e){
    if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); flip(); }
  });
});
document.querySelectorAll('[data-expand]').forEach(function(btn){
  btn.addEventListener('click', function(){
    var open = btn.getAttribute('data-expand') === '1';
    document.querySelectorAll('.brow').forEach(function(row){
      if(row.querySelector(':scope > .ncard.toggle')) setOpen(row, open);
    });
    document.querySelectorAll('details.node').forEach(function(d){ d.open = open; });
  });
});
"""

# public aliases so larger pages (blog posts, composed reports) can reuse the styling
CSS = _CSS
JS = _JS

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


def _card_inner(node: dict[str, Any], max_abs: float) -> str:
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
    return (
        f'<div class="n-top"><span class="n-act">{_esc(node.get("action", ""))}</span>'
        f"{role_html}{chip}{_score_bar(node, max_abs)}</div>{note_html}{line_html}"
    )


def _li_class(node: dict[str, Any]) -> str:
    verdict = str(node.get("verdict", ""))
    if verdict == "selected":
        return "sel"
    if verdict == "refuted":
        return "ref"
    return ""


def _render_hnode(node: dict[str, Any], max_abs: float, depth: int) -> str:
    verdict = str(node.get("verdict", ""))
    children = node.get("children") or []
    is_root = bool(node.get("_root"))
    expanded = is_root or verdict == "selected" or depth > 0
    row_classes = ["brow"]
    if _li_class(node):
        row_classes.append(_li_class(node))
    if expanded and children:
        row_classes.append("open")
    toggleable = bool(children) and not is_root
    card_classes = ["ncard", "root" if is_root else "", f"v-{verdict}" if verdict else "", "toggle" if toggleable else ""]
    caret = '<span class="caret" aria-hidden="true">&#9656;</span>' if toggleable else ""
    toggle_attrs = (
        f' role="button" tabindex="0" aria-expanded="{"true" if expanded else "false"}"' if toggleable else ""
    )
    card = (
        f'<div class="{" ".join(c for c in card_classes if c)}"{toggle_attrs}>'
        f"{_card_inner(node, max_abs)}{caret}</div>"
    )
    kids = ""
    stub = ""
    if children:
        stub = '<div class="stub"></div>'
        items = "".join(
            f'<li class="{_li_class(c)}">{_render_hnode(c, max_abs, depth + 1)}</li>' for c in children
        )
        kids = f'<ul class="kids">{items}</ul>'
    collapsed = "0" if (expanded or not children) else "1"
    return f'<div class="{" ".join(row_classes)}" data-collapsed="{collapsed}">{card}{stub}{kids}</div>'


def _render_vnode(node: dict[str, Any], max_abs: float, depth: int) -> str:
    verdict = str(node.get("verdict", ""))
    children = node.get("children") or []
    caret = '<span class="caret-v">&#9656;</span> ' if children else ""
    summary = f"<summary>{caret}{_card_inner(node, max_abs)}</summary>"
    kids_html = ""
    if children:
        inner = "".join(f"<li>{_render_vnode(c, max_abs, depth + 1)}</li>" for c in children)
        kids_html = f'<div class="dkids"><ul class="vtree">{inner}</ul></div>'
    open_attr = " open" if verdict == "selected" and depth == 0 else ""
    classes = f"node v-{verdict}" if verdict else "node"
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

    items: list[tuple[float, str]] = []
    for ex in raw.get("excerpts", []):
        t = float(ex.get("t", 0))
        items.append(
            (t, f'<div><span class="tick">t = {_esc(ex.get("t", "?"))}s</span>'
                f'<p>{_esc(ex.get("text", ""))} <span class="ellipsis">&hellip;</span></p></div>')
        )
    for marker in raw.get("markers", []):
        t = float(marker.get("t", 0))
        items.append(
            (t, f'<div><hr class="cut"><span class="cutlabel">t = {_esc(marker.get("t", "?"))}s &mdash; '
                f"{_esc(marker.get('label', ''))}</span></div>")
        )
    items.sort(key=lambda pair: pair[0])
    parts = [chunk for _, chunk in items]

    tail = ""
    if final.get("predicted"):
        verdict = "correct" if final.get("correct") else "wrong"
        expected = f" (expected {_esc(final['expected'])})" if final.get("expected") and not final.get("correct") else ""
        note = f" &mdash; {_esc(final['note'])}" if final.get("note") else ""
        tail = (
            f'<div><hr class="cut"><span class="cutlabel">t = {_esc(final.get("wall_seconds", "?"))}s &mdash; finally '
            f"commits to {_esc(final['predicted'])} — {verdict}{expected}{note}</span></div>"
        )
    elif raw.get("unfinished"):
        tail = (
            '<div><hr class="cut"><span class="cutlabel">still generating when the budget ended — '
            'no move was ever committed</span> <span class="ellipsis">&hellip;</span></div>'
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


def render_panes(spec: dict[str, Any]) -> str:
    """Return just the raw-trace and tree panes, for embedding in larger pages."""
    nodes = spec.get("nodes") or []
    scores = _collect_scores(nodes)
    max_abs = max(scores) if scores else 1.0
    layout = spec.get("layout", "horizontal")
    budget = spec.get("budget") or {}
    budget_chips = "".join(
        f'<span class="chip mut">{_esc(k.replace("_", " "))}: {_esc(v)}</span>' for k, v in budget.items()
    )
    state = spec.get("state")
    state_html = f'<pre class="state">{_esc(state)}</pre>' if state else ""

    if layout == "horizontal":
        root_label = spec.get("root_label")
        if root_label and nodes:
            trunk = {"action": root_label, "role": "state", "children": nodes, "_root": True}
            tree_items = _render_hnode(trunk, max_abs, -1)
        else:
            tree_items = "".join(_render_hnode(n, max_abs, 0) for n in nodes)
        tree_html = (
            f'<div class="htree-scroll"><div class="htree">{tree_items}</div></div>'
            '<div class="legend">'
            '<span class="li"><span class="sw selline"></span>selected path</span>'
            '<span class="li"><span class="sw survline"></span>surviving branch</span>'
            '<span class="li"><span class="sw refline"></span>refuted branch</span>'
            '<span class="li">click a node to open its counter-branches</span></div>'
        )
    else:
        tree_items = "".join(f"<li>{_render_vnode(n, max_abs, 0)}</li>" for n in nodes)
        tree_html = f'<ul class="vtree">{tree_items}</ul>'

    selected = spec.get("selected_action")
    selection_note = spec.get(
        "selection_note", "the branch that survives the opponent&rsquo;s strongest reply within the budget."
    )
    verdict_html = (
        f'<div class="verdictline">Controller selection: <b>{_esc(selected)}</b> &mdash; {selection_note}</div>'
        if selected
        else ""
    )
    tree_pane = (
        '<section class="pane"><div class="pane-h"><span class="t">ReasonTree bounded search</span>'
        '<span class="chip ok badge"><span class="dot"></span>every branch inspectable</span></div>'
        f'<div class="pane-b">{state_html}<div class="budget">{budget_chips}</div>'
        '<div class="controls"><button type="button" data-expand="1">Expand all</button>'
        '<button type="button" data-expand="0">Collapse all</button></div>'
        f"{tree_html}{verdict_html}</div></section>"
    )
    raw = spec.get("raw_trace")
    return (_render_raw_pane(raw) + tree_pane) if raw else tree_pane


def render_body(spec: dict[str, Any]) -> str:
    panes = render_panes(spec)
    board_svg = spec.get("board_svg")
    board_html = ""
    if board_svg:
        caption = spec.get("board_caption")
        caption_html = f"<figcaption>{_esc(caption)}</figcaption>" if caption else ""
        board_html = f'<figure class="board" role="img">{board_svg}{caption_html}</figure>'
    header = (
        f'<div class="hero"><div class="intro">'
        f'<div class="eyebrow">{_esc(spec.get("eyebrow", "ReasonTree artifact"))}</div>'
        f'<h1 class="serif">{_esc(spec.get("title", "ReasonTree search"))}</h1>'
        f'<p class="task">{_esc(spec.get("task", ""))}</p></div>{board_html}</div>'
    )
    return (
        f'<div class="wrap">{header}<div class="stack">{panes}</div>'
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
