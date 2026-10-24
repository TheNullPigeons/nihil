#!/usr/bin/env python3
"""Local browser UI for image customization and build progress."""

from __future__ import annotations

import hmac
import html
import json
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit


_PENDING = object()
_MAX_FORM_BYTES = 1_000_000


def _disabled_from_enabled(tools: list[dict], enabled: set[str]) -> set[str]:
    """Validate submitted names and return disabled optional tools."""
    optional = {tool["name"] for tool in tools if not tool["mandatory"]}
    return optional - (enabled & optional)


def _render_result(title: str, message: str, success: bool) -> bytes:
    icon = "✓" if success else "×"
    tone = "success" if success else "cancelled"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{html.escape(title)}</title><style>
@import url('https://fonts.googleapis.com/css2?family=Big+Shoulders:wght@500..900&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
:root {{ color-scheme:dark; font-family:'IBM Plex Sans',system-ui,sans-serif; background:#141416; color:#f3eee5 }}
* {{ box-sizing:border-box }} body {{ min-height:100vh; margin:0; background:#141416; color:#f3eee5 }} .airmail-bar {{ height:7px; background-image:repeating-linear-gradient(-45deg,#b45309 0 12px,transparent 12px 20px,#2c57c8 20px 32px,transparent 32px 40px) }}
.card {{ width:min(760px,calc(100% - 48px)); margin:12vh auto; padding:42px; border:6px solid transparent; background:linear-gradient(#19191c,#19191c) padding-box,repeating-linear-gradient(-45deg,#b45309 0 14px,#f3eee5 14px 22px,#238bd3 22px 36px,#f3eee5 36px 44px) border-box; box-shadow:9px 9px 0 #0b0b0c }}
.icon {{ display:grid; width:58px; height:58px; margin:0 0 22px; place-items:center; border:1px solid #49464b; font-size:30px; font-weight:800 }}
.success {{ color:#32b4e3 }} .cancelled {{ color:#b45309 }}
h1 {{ margin:0 0 10px; font:800 clamp(36px,6vw,58px)/1 'Big Shoulders','Arial Narrow',sans-serif; text-transform:uppercase }} p {{ margin:0; color:#aaa6a3; line-height:1.6 }}
.brand {{ margin-top:28px; color:#918d8c; font:11px 'IBM Plex Mono',monospace; letter-spacing:.14em; text-transform:uppercase }} .brand b {{ color:#32b4e3 }}
</style></head><body><div class="airmail-bar"></div><main class="card"><div class="icon {tone}">{icon}</div><h1>{html.escape(title)}</h1>
<p>{html.escape(message)}</p><div class="brand"><b>Nihil</b> · TheNullPigeons</div></main></body></html>""".encode()


def _render_page(
    tools: list[dict], disabled: set[str], title: str, token: str,
    action_label: str = "Apply selection",
) -> bytes:
    categories: dict[str, list[dict]] = {}
    for tool in tools:
        categories.setdefault(tool["category"], []).append(tool)

    required_count = sum(tool["mandatory"] for tool in tools)
    selected_count = sum(tool["mandatory"] or tool["name"] not in disabled for tool in tools)
    category_options = "".join(
        f'<option value="{html.escape(category, quote=True)}">{html.escape(category)}</option>'
        for category in categories
    )
    groups = []
    for category, entries in categories.items():
        category_search = html.escape(category.lower(), quote=True)
        category_value = html.escape(category, quote=True)
        optional_entries = [tool for tool in entries if not tool["mandatory"]]
        category_checked = " checked" if all(tool["name"] not in disabled for tool in optional_entries) else ""
        category_locked = " disabled" if not optional_entries else ""
        rows = []
        for tool in entries:
            name = html.escape(tool["name"], quote=True)
            command = html.escape(str(tool.get("cmd") or "-"))
            mandatory = tool["mandatory"]
            checked = " checked" if mandatory or tool["name"] not in disabled else ""
            locked = " disabled" if mandatory else ""
            badge = '<span class="required">required</span>' if mandatory else ""
            rows.append(
                f'<label class="tool" data-search="{name.lower()} {command.lower()} {category_search}" '
                f'data-category="{category_value}">'
                f'<input type="checkbox" name="enabled" value="{name}"{checked}{locked}>'
                f'<span class="checkmark"></span><span class="tool-copy"><b>{name}</b>'
                f'<code>$ {command}</code></span>{badge}</label>'
            )
        groups.append(
            f'<section class="group" data-group><div class="group-head"><label class="category-toggle">'
            f'<input type="checkbox" data-category-toggle="{category_value}"{category_checked}{category_locked}>'
            f'<span class="category-check"></span><h2>{html.escape(category)}</h2></label>'
            f'<span class="group-count">{len(entries)} tools</span></div><div class="tool-grid">{"".join(rows)}</div></section>'
        )

    action = "/save?" + urlencode({"token": token})
    cancel = "/cancel?" + urlencode({"token": token})
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Nihil tool selector</title><style>
@import url('https://fonts.googleapis.com/css2?family=Big+Shoulders:wght@500..900&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
:root {{ color-scheme:dark; font-family:'IBM Plex Sans',system-ui,sans-serif; background:#141416; color:#f3eee5; accent-color:#32b4e3 }}
* {{ box-sizing:border-box }} body {{ margin:0; min-height:100vh; background-color:#141416; background-image:linear-gradient(#232226 1px,transparent 1px),linear-gradient(90deg,#232226 1px,transparent 1px); background-size:32px 32px }}
body:after {{ content:''; position:fixed; inset:0; z-index:5; pointer-events:none; opacity:.055; mix-blend-mode:overlay; background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>") }}
.airmail-bar {{ height:7px; background-image:repeating-linear-gradient(-45deg,#b45309 0 12px,transparent 12px 20px,#2c57c8 20px 32px,transparent 32px 40px) }}
.site-head {{ position:sticky; top:0; z-index:4; border-bottom:1px solid #333136; background:#141416ed; backdrop-filter:blur(16px) }}
.site-head-inner {{ display:flex; align-items:center; justify-content:space-between; width:min(1760px,calc(100% - 64px)); height:78px; margin:auto }}
.brand {{ display:flex; align-items:center; gap:14px }} .brand-copy {{ display:flex; flex-direction:column; gap:4px }} .brand-copy strong {{ color:#f3eee5; font:800 25px/1 'Big Shoulders','Arial Narrow',sans-serif; text-transform:uppercase }} .brand-copy small {{ color:#918d8c; font:10px 'IBM Plex Mono',monospace; letter-spacing:.15em; text-transform:uppercase }}
.brand-mark {{ display:grid; place-items:center; width:42px; height:42px; border:1px solid #49464b; color:#32b4e3; font:800 28px/1 'Big Shoulders','Arial Narrow',sans-serif; box-shadow:3px 3px 0 #b45309 }}
.local-badge {{ display:flex; align-items:center; gap:8px; padding:8px 11px; border:1px solid #333136; color:#aaa6a3; font:10px 'IBM Plex Mono',monospace; letter-spacing:.1em; text-transform:uppercase }} .local-badge:before {{ content:''; width:7px; height:7px; background:#32b4e3 }}
.page {{ width:min(1760px,calc(100% - 64px)); margin:auto; padding:38px 0 120px }}
.hero {{ display:flex; justify-content:space-between; align-items:end; gap:24px; margin:0 0 30px }}
h1 {{ margin:0 0 8px; color:#f3eee5; font:800 clamp(42px,6vw,72px)/.95 'Big Shoulders','Arial Narrow',sans-serif; letter-spacing:.005em; text-transform:uppercase }} .subtitle {{ color:#aaa6a3 }}
.stats {{ display:flex; gap:8px; flex-wrap:wrap }} .stat {{ min-width:100px; padding:12px 15px; border:1px solid #333136; background:#19191c }}
.stat b {{ display:block; color:#32b4e3; font:600 23px 'IBM Plex Mono',monospace }} .stat small {{ color:#918d8c; font:10px 'IBM Plex Mono',monospace; text-transform:uppercase; letter-spacing:.1em }}
.filters {{ position:sticky; top:88px; z-index:2; display:grid; grid-template-columns:minmax(220px,1fr) 190px 180px auto; gap:10px; padding:12px; border:1px solid #49464b; background:#19191cf2; box-shadow:6px 6px 0 #0b0b0c; backdrop-filter:blur(12px) }}
input[type=search],select {{ width:100%; min-height:44px; border:1px solid #49464b; padding:0 12px; background:#141416; color:#f3eee5; font:13px 'IBM Plex Sans',sans-serif; outline:none }}
input[type=search]:focus,select:focus {{ border-color:#32b4e3; box-shadow:0 0 0 2px #32b4e333 }}
.toggle-buttons {{ display:flex; gap:6px }} button,.cancel {{ border:1px solid #49464b; padding:10px 14px; background:#232226; color:#f3eee5; cursor:pointer; text-decoration:none; font:12px 'IBM Plex Mono',monospace; text-transform:uppercase; white-space:nowrap }}
button:hover,.cancel:hover {{ border-color:#32b4e3; color:#32b4e3 }}
.group {{ margin-top:26px }} .group-head {{ display:flex; align-items:center; justify-content:space-between; margin:0 2px 10px }}
.category-toggle {{ display:flex; align-items:center; gap:9px; cursor:pointer }} .category-toggle input {{ position:absolute; opacity:0 }} .category-check {{ display:grid; place-items:center; width:17px; height:17px; border:1px solid #686568; background:#19191c }}
.category-toggle input:checked + .category-check {{ border-color:#32b4e3; background:#32b4e3 }} .category-toggle input:checked + .category-check:after {{ content:'✓'; color:#141416; font-size:12px; font-weight:900 }} .category-toggle input:indeterminate + .category-check {{ border-color:#32b4e3; background:#32b4e3 }} .category-toggle input:indeterminate + .category-check:after {{ content:'−'; color:#141416; font-weight:900 }}
.group h2 {{ margin:0; color:#aaa6a3; font:600 13px 'IBM Plex Mono',monospace; letter-spacing:.12em; text-transform:uppercase }} .group-count {{ color:#918d8c; font:11px 'IBM Plex Mono',monospace }}
.tool-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px }}
.tool {{ position:relative; display:flex; align-items:center; gap:12px; min-width:0; padding:14px; border:1px solid #333136; background:#19191ce8; cursor:pointer; transition:border-color .15s,background .15s }}
.tool:hover {{ border-color:#686568; background:#232226 }} .tool:has(input:checked) {{ border-color:#32b4e388; background:linear-gradient(135deg,#32b4e318,#19191c 72%) }}
.tool input {{ position:absolute; opacity:0; pointer-events:none }} .checkmark {{ flex:none; width:20px; height:20px; border:1px solid #686568 }}
.tool input:checked + .checkmark {{ border-color:#32b4e3; background:#32b4e3 }} .tool input:checked + .checkmark:after {{ content:'✓'; display:block; color:#141416; text-align:center; font-weight:900; line-height:18px }}
.tool-copy {{ min-width:0; display:flex; flex:1; flex-direction:column; gap:4px }} .tool-copy b {{ overflow:hidden; color:#f3eee5; text-overflow:ellipsis; font-size:14px }} code {{ overflow:hidden; color:#918d8c; font:10px 'IBM Plex Mono',monospace; text-overflow:ellipsis }}
.required {{ align-self:flex-start; color:#b45309; font:9px 'IBM Plex Mono',monospace; letter-spacing:.08em; text-transform:uppercase }} .tool:has(input:disabled) {{ cursor:default }}
.actions {{ position:fixed; z-index:3; right:0; bottom:0; left:0; border-top:1px solid #333136; background:#141416ed; backdrop-filter:blur(16px) }} .actions-inner {{ display:flex; align-items:center; justify-content:space-between; width:min(1760px,calc(100% - 64px)); margin:auto; padding:14px 0 }}
.selection {{ color:#aaa6a3; font-size:13px }} .selection strong {{ color:#32b4e3 }} .action-buttons {{ display:flex; gap:8px }} button.primary {{ border-color:#32b4e3; background:#32b4e3; color:#141416; font-weight:700; box-shadow:3px 3px 0 #b45309 }} button.primary:hover {{ background:#57c7ec; color:#141416 }}
.hidden {{ display:none }} .empty {{ display:none; padding:70px 20px; color:#918d8c; text-align:center; font-family:'IBM Plex Mono',monospace }} .empty.visible {{ display:block }}
@media(max-width:850px) {{ .hero {{ align-items:start; flex-direction:column }} .filters {{ grid-template-columns:1fr 1fr }} .filters input {{ grid-column:1/-1 }} .tool-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)) }} }}
@media(max-width:540px) {{ .page {{ width:min(100% - 20px,1180px); padding-top:24px }} .filters,.tool-grid {{ grid-template-columns:1fr }} .filters select,.toggle-buttons {{ grid-column:1 }} .toggle-buttons button {{ flex:1 }} .stats {{ width:100% }} .stat {{ flex:1 }} .selection {{ display:none }} }}
</style></head><body>
<div class="airmail-bar"></div><header class="site-head"><div class="site-head-inner"><div class="brand"><span class="brand-mark">N</span><span class="brand-copy"><strong>TheNullPigeons</strong><small>Nihil image customizer</small></span></div><span class="local-badge">Local session</span></div></header>
<main class="page"><div class="hero"><div><h1>Choose your tools.</h1><div class="subtitle">Customize <strong>{html.escape(title)}</strong> without the bloat.</div></div>
<div class="stats"><div class="stat"><b>{len(tools)}</b><small>available</small></div><div class="stat"><b id="stat-selected">{selected_count}</b><small>selected</small></div><div class="stat"><b>{required_count}</b><small>required</small></div></div></div>
<form method="post" action="{action}"><div class="filters">
<input id="search" type="search" placeholder="Search tools or commands…" aria-label="Search tools" autofocus>
<select id="category" aria-label="Filter by category"><option value="">All categories</option>{category_options}</select>
<select id="status" aria-label="Filter by status"><option value="">Any status</option><option value="selected">Selected</option><option value="disabled">Disabled</option><option value="required">Required</option></select>
<div class="toggle-buttons"><button type="button" onclick="toggle(true)">All</button><button type="button" onclick="toggle(false)">None</button></div>
</div>{''.join(groups)}<div id="empty" class="empty">No tools match these filters.</div>
<div class="actions"><div class="actions-inner"><span class="selection"><strong id="selected">{selected_count}</strong> of {len(tools)} tools selected</span><div class="action-buttons"><a class="cancel" href="{cancel}">Cancel</a><button class="primary" type="submit">{html.escape(action_label)} →</button></div></div></div></form></main>
<script>
const tools=[...document.querySelectorAll('.tool')];
const categoryToggles=[...document.querySelectorAll('[data-category-toggle]')];
const search=document.querySelector('#search'),category=document.querySelector('#category'),status=document.querySelector('#status');
function filter(){{
 const q=search.value.toLowerCase(),cat=category.value,state=status.value;
 tools.forEach(x=>{{const c=x.querySelector('input');const matchesState=!state||(state==='selected'&&c.checked)||(state==='disabled'&&!c.checked)||(state==='required'&&c.disabled);x.classList.toggle('hidden',!x.dataset.search.includes(q)||(cat&&x.dataset.category!==cat)||!matchesState)}});
 document.querySelectorAll('[data-group]').forEach(g=>g.classList.toggle('hidden',!g.querySelector('.tool:not(.hidden)')));
 document.querySelector('#empty').classList.toggle('visible',!document.querySelector('.tool:not(.hidden)'));
}}
function syncCategories(){{categoryToggles.forEach(c=>{{const members=tools.filter(x=>x.dataset.category===c.dataset.categoryToggle&&!x.querySelector('input').disabled);const selected=members.filter(x=>x.querySelector('input').checked).length;c.checked=selected===members.length;c.indeterminate=selected>0&&selected<members.length}})}}
function update(){{const count=tools.filter(x=>x.querySelector('input').checked).length;document.querySelector('#selected').textContent=count;document.querySelector('#stat-selected').textContent=count;syncCategories();filter()}}
[search,category,status].forEach(x=>x.addEventListener(x===search?'input':'change',filter));tools.forEach(x=>x.querySelector('input').addEventListener('change',update));
categoryToggles.forEach(c=>c.addEventListener('change',()=>{{tools.filter(x=>x.dataset.category===c.dataset.categoryToggle).forEach(x=>{{const input=x.querySelector('input');if(!input.disabled)input.checked=c.checked}});update()}}));
function toggle(value){{tools.forEach(x=>{{const c=x.querySelector('input');if(!c.disabled)c.checked=value}});update()}}
syncCategories();
</script></body></html>"""
    return document.encode()


def _render_progress_page(
    token: str, can_cancel: bool = False, *, page_context: str = "Nihil · GitHub Actions",
    page_title: str = "Building your image…", success_title: str = "Customization complete",
    initial_label: str = "Preparing customization",
    plain_logs: bool = False,
) -> bytes:
    status_url = "/status?" + urlencode({"token": token})
    logs_url = "/logs?" + urlencode({"token": token})
    cancel_url = "/cancel-build?" + urlencode({"token": token})
    cancel_button = '<button id="cancel-build" type="button">Cancel build</button>' if can_cancel else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{html.escape(page_context)}</title><style>
@import url('https://fonts.googleapis.com/css2?family=Big+Shoulders:wght@500..900&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
:root {{ color-scheme:dark; font-family:'IBM Plex Sans',system-ui,sans-serif; background:#141416; color:#f3eee5 }}
* {{ box-sizing:border-box }} body {{ min-height:100vh; margin:0; padding:0 0 28px; background-color:#141416; background-image:linear-gradient(#232226 1px,transparent 1px),linear-gradient(90deg,#232226 1px,transparent 1px); background-size:32px 32px }} body:after {{ content:''; position:fixed; inset:0; z-index:5; pointer-events:none; opacity:.055; mix-blend-mode:overlay; background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>") }}
.airmail-bar {{ height:7px; background-image:repeating-linear-gradient(-45deg,#b45309 0 12px,transparent 12px 20px,#2c57c8 20px 32px,transparent 32px 40px) }} .site-head {{ width:min(1760px,calc(100% - 64px)); height:88px; margin:auto; display:flex; align-items:center; gap:16px; border-bottom:1px solid #333136 }} .brand-mark {{ width:44px; height:44px; display:grid; place-items:center; border:1px solid #49464b; color:#32b4e3; font:800 30px/1 'Big Shoulders','Arial Narrow',sans-serif; box-shadow:3px 3px 0 #b45309 }} .brand-copy {{ display:flex; flex-direction:column; gap:4px }} .brand-name {{ color:#f3eee5; font:800 26px/1 'Big Shoulders','Arial Narrow',sans-serif; text-transform:uppercase; letter-spacing:.02em }} .brand-caption {{ color:#918d8c; font:10px 'IBM Plex Mono',ui-monospace,monospace; letter-spacing:.18em; text-transform:uppercase }} .session-tag {{ margin-left:auto; border:1px solid #333136; padding:8px 11px; color:#aaa6a3; font:10px 'IBM Plex Mono',ui-monospace,monospace; letter-spacing:.12em; text-transform:uppercase }} .session-tag span {{ color:#32b4e3 }}
.card {{ width:min(1760px,calc(100% - 64px)); min-height:calc(100vh - 132px); margin:24px auto 0; padding:42px; border:6px solid transparent; background:linear-gradient(#19191c,#19191c) padding-box,repeating-linear-gradient(-45deg,#b45309 0 14px,#f3eee5 14px 22px,#238bd3 22px 36px,#f3eee5 36px 44px) border-box; box-shadow:9px 9px 0 #0b0b0c }} .summary {{ width:100%; margin:0 auto }}
.eyebrow {{ display:flex; align-items:center; gap:8px; color:#32b4e3; font:500 11px 'IBM Plex Mono',ui-monospace,monospace; letter-spacing:.18em; text-transform:uppercase }} .pulse {{ width:7px; height:7px; border-radius:0; background:#32b4e3; box-shadow:0 0 0 0 #32b4e388; animation:pulse 1.5s infinite }} h1 {{ margin:12px 0 8px; color:#f3eee5; font:800 clamp(42px,6vw,72px)/.95 'Big Shoulders','Arial Narrow',sans-serif; letter-spacing:.005em; text-transform:uppercase }}
#label {{ min-height:32px; margin:14px 0 0; color:#32b4e3; font:500 clamp(18px,2vw,25px)/1.3 'IBM Plex Sans',sans-serif }} #detail {{ color:#aaa6a3 }} #label.changed {{ animation:step-change .4s ease }} .progress-track {{ width:100%; height:12px; margin:24px 0 12px; overflow:hidden; border-radius:2px; background:#333136 }} .progress-fill {{ width:0; height:100%; border-radius:inherit; background:linear-gradient(90deg,#b45309,#f3eee5,#32b4e3,#238bd3); background-size:200% 100%; box-shadow:0 0 16px #32b4e333; transition:width .7s cubic-bezier(.22,1,.36,1); animation:shimmer 1.4s linear infinite }} .progress-track.indeterminate .progress-fill {{ width:35%; animation:indeterminate 1.25s ease-in-out infinite,shimmer 1.4s linear infinite }}
.meta {{ display:flex; justify-content:space-between; gap:16px; color:#918d8c; font:12px 'IBM Plex Mono',ui-monospace,monospace }}
a {{ display:none; margin-top:24px; color:#32b4e3 }} a.has-run {{ display:inline-block }} button {{ float:right; margin-top:18px; padding:10px 15px; border:1px solid #b45309; border-radius:2px; background:#b45309; color:#f3eee5; cursor:pointer; font:600 11px 'IBM Plex Mono',ui-monospace,monospace; letter-spacing:.1em; text-transform:uppercase }} button:disabled {{ cursor:default; opacity:.55 }} .done button {{ display:none }} .done .pulse {{ animation:none }} .failed .eyebrow {{ color:#dc4a3c }} .failed .progress-fill {{ background:#dc4a3c }}
.logs {{ display:none; clear:both; margin-top:28px; padding-top:20px; border-top:1px solid #333136 }} .has-logs .logs {{ display:block }} .logs-head {{ display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:10px; border-bottom:1px solid #333136; padding-bottom:10px }} .logs h2 {{ margin:0; color:#f3eee5; font:700 24px 'Big Shoulders','Arial Narrow',sans-serif; letter-spacing:.06em; text-transform:uppercase }} .logs a {{ display:inline; margin:0; font:11px 'IBM Plex Mono',ui-monospace,monospace; text-transform:uppercase }} pre {{ width:100%; height:calc(100vh - 365px); min-height:460px; margin:0; padding:20px; overflow:auto; border:1px solid #333136; border-radius:2px; background:#101012; color:#e0dcd5; font:12px/1.6 'IBM Plex Mono',ui-monospace,monospace; white-space:pre; tab-size:2; scrollbar-color:#49464b transparent }}
.log-line {{ display:block }} .log-job {{ color:#32b4e3 }} .log-step {{ color:#b45309 }} .log-time {{ color:#918d8c }} .log-error {{ color:#dc4a3c }} .log-warning {{ color:#b45309 }} .log-success {{ color:#32b4e3 }}
@keyframes pulse {{ 70% {{ box-shadow:0 0 0 8px #32b4e300 }} 100% {{ box-shadow:0 0 0 0 #32b4e300 }} }} @keyframes shimmer {{ to {{ background-position:-200% 0 }} }} @keyframes indeterminate {{ from {{ transform:translateX(-120%) }} to {{ transform:translateX(330%) }} }} @keyframes step-change {{ 50% {{ color:#32b4e3; transform:translateX(4px) }} }}
@media(prefers-reduced-motion:reduce) {{ .pulse,.progress-fill,.progress-track.indeterminate .progress-fill,#label.changed {{ animation:none }} .progress-fill {{ transition:none }} }}
@media(max-width:700px) {{ .site-head {{ width:calc(100% - 32px); height:72px }} .brand-name {{ font-size:21px }} .session-tag {{ padding:6px 8px; font-size:9px }} .card {{ width:calc(100% - 24px); min-height:calc(100vh - 100px); margin-top:14px; padding:24px 18px }} pre {{ height:60vh; min-height:340px; padding:12px; font-size:11px }} .meta {{ align-items:flex-start; flex-direction:column; gap:4px }} }}
</style></head><body><div class="airmail-bar"></div><header class="site-head"><span class="brand-mark">N</span><div class="brand-copy"><span class="brand-name">TheNullPigeons</span><span class="brand-caption">Nihil · Image operations</span></div><span class="session-tag"><span>●</span> Local session</span></header><main id="card" class="card"><div class="summary"><div class="eyebrow"><span class="pulse"></span>{html.escape(page_context)} / BUILD PIPELINE</div><h1 id="title">{html.escape(page_title)}</h1>
<p id="label">{html.escape(initial_label)}</p><div id="bar" class="progress-track indeterminate" role="progressbar" aria-label="Build progress"><div class="progress-fill"></div></div><div class="meta"><span id="detail">Starting…</span><span><span id="elapsed">00:00</span> · <span id="percent">waiting</span></span></div>
<a id="run" target="_blank" rel="noreferrer">View live logs on GitHub →</a>{cancel_button}</div><section class="logs"><div class="logs-head"><h2>Complete build logs</h2><a id="download" download="nihil-build.log">Download logs</a></div><pre id="logs"></pre></section></main>
<script>
const card=document.querySelector('#card'),bar=document.querySelector('#bar'),fill=bar.querySelector('.progress-fill'),label=document.querySelector('#label'),detail=document.querySelector('#detail'),percent=document.querySelector('#percent'),elapsed=document.querySelector('#elapsed'),run=document.querySelector('#run'),cancel=document.querySelector('#cancel-build'),logs=document.querySelector('#logs'),download=document.querySelector('#download'),started=Date.now();let lastLabel='',lastLogVersion=-1,downloadUrl='';
const clock=setInterval(()=>{{const seconds=Math.floor((Date.now()-started)/1000);elapsed.textContent=String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0')}},1000);
if(cancel)cancel.addEventListener('click',async()=>{{cancel.disabled=true;cancel.textContent='Cancellation requested…';await fetch('{cancel_url}',{{method:'POST'}})}});
function renderAnsiLogs(text){{
 const colors={{30:'#141416',31:'#dc4a3c',32:'#78b77a',33:'#e9b949',34:'#32b4e3',35:'#d393dc',36:'#57c7ec',37:'#f3eee5',90:'#918d8c',91:'#dc4a3c',92:'#78b77a',93:'#e9b949',94:'#32b4e3',95:'#d393dc',96:'#57c7ec',97:'#faf7f2'}};
 const parts=text.split(/\\u001b\\[([0-9;]*)m/g),fragment=document.createDocumentFragment();let color=null,bold=false;
 for(let i=0;i<parts.length;i++){{if(i%2){{for(const raw of parts[i].split(';')){{const code=Number(raw||0);if(code===0){{color=null;bold=false}}else if(code===1)bold=true;else if(code===22)bold=false;else if(code===39)color=null;else if(colors[code])color=colors[code]}}continue}}
  const lines=parts[i].split('\\n');for(let j=0;j<lines.length;j++){{const line=lines[j];if(line){{const span=document.createElement('span');const fallback=/\\b(error|failed|failure|fatal)\\b/i.test(line)?'#dc4a3c':/\\b(warn|warning)\\b/i.test(line)?'#e9b949':line.includes('[NIHIL]')?'#32b4e3':/\\b(success|succeeded|installed|complete|completed)\\b/i.test(line)?'#78b77a':null;span.style.color=color||fallback||'';if(bold)span.style.fontWeight='600';span.textContent=line;fragment.append(span)}}if(j<lines.length-1)fragment.append(document.createTextNode('\\n'))}}
 }}logs.replaceChildren(fragment)
}}
function renderLogs(text){{const follow=logs.scrollHeight-logs.scrollTop-logs.clientHeight<24,previousTop=logs.scrollTop;if({str(plain_logs).lower()})renderAnsiLogs(text);else{{const fragment=document.createDocumentFragment();for(const line of text.split('\\n')){{const row=document.createElement('span');row.className='log-line';const parts=line.split('\\t');const message=parts.length>3?parts.slice(3).join('\\t'):line;if(parts.length>3){{for(const [value,className] of [[parts[0],'log-job'],[parts[1],'log-step'],[parts[2],'log-time']]){{const part=document.createElement('span');part.className=className;part.textContent=value;row.append(part,document.createTextNode('\\t'))}}}}const content=document.createElement('span');content.textContent=message;if(/\\b(error|failed|failure|fatal)\\b/i.test(message))content.className='log-error';else if(/\\b(warn|warning)\\b/i.test(message))content.className='log-warning';else if(/\\b(success|succeeded|complete|completed|passed)\\b/i.test(message))content.className='log-success';row.append(content);fragment.append(row)}}logs.replaceChildren(fragment)}}logs.scrollTop=follow?logs.scrollHeight:previousTop}}
async function poll(){{try{{const response=await fetch('{status_url}',{{cache:'no-store'}});const state=await response.json();if(state.label!==lastLabel){{lastLabel=state.label;label.textContent=state.label;label.classList.remove('changed');void label.offsetWidth;label.classList.add('changed')}}if(state.total>0){{const value=Math.round(state.completed/state.total*100);bar.classList.remove('indeterminate');fill.style.width=value+'%';bar.setAttribute('aria-valuenow',value);bar.setAttribute('aria-valuetext',state.label+' · '+state.completed+' / '+state.total+' phases');percent.textContent=value+'%';detail.textContent=state.completed+' / '+state.total+' phases complete'}}else{{bar.classList.add('indeterminate');fill.style.width='';bar.removeAttribute('aria-valuenow');bar.setAttribute('aria-valuetext',state.label);percent.textContent='waiting';detail.textContent='Waiting for phase information…'}}if(state.url){{run.href=state.url;run.classList.add('has-run')}}if(state.logs_ready&&state.log_version!==lastLogVersion){{const response=await fetch('{logs_url}',{{cache:'no-store'}});if(!response.ok)throw new Error('Build output is unavailable');const text=await response.text(),wasHidden=!card.classList.contains('has-logs');renderLogs(text);if(downloadUrl)URL.revokeObjectURL(downloadUrl);downloadUrl=URL.createObjectURL(new Blob([text],{{type:'text/plain'}}));download.href=downloadUrl;card.classList.add('has-logs');if(wasHidden)logs.scrollTop=logs.scrollHeight;lastLogVersion=state.log_version}}if(state.done){{clearInterval(clock);card.classList.add('done');document.querySelector('#title').textContent=state.success?'{html.escape(success_title)}':state.cancelled?'Build cancelled':'Build failed';if(state.success)fill.style.width='100%';if(!state.success&&!state.cancelled)card.classList.add('failed');detail.textContent=state.success?'Build complete.':state.error;return}}}}catch(error){{label.textContent='Connection to Nihil lost';detail.textContent=error}}setTimeout(poll,1000)}}poll();
</script></body></html>""".encode()


def select_tools_web(
    tools: list[dict], disabled: set[str], title: str, *, on_save=None,
    action_label: str = "Apply selection", can_cancel: bool = False,
    start_immediately: bool = False, page_context: str = "Nihil · GitHub Actions",
    page_title: str = "Building your image…", success_title: str = "Customization complete",
    initial_label: str = "Preparing customization",
    plain_logs: bool = False,
) -> set[str] | None:
    """Open a one-session localhost selector or progress page and wait for completion."""
    token = secrets.token_urlsafe(24)
    state: dict[str, object] = {
        "result": _PENDING,
        "progress": {"completed": 0, "total": 0, "label": "Preparing customization", "url": ""},
        "done": False,
        "success": False,
        "cancelled": False,
        "error": "",
        "logs": "",
        "reported": False,
        "log_version": 0,
    }
    cancel_event = threading.Event()

    def report(
        completed: int, total: int, label: str, url: str = "", logs: str | None = None,
    ) -> None:
        state["progress"] = {"completed": completed, "total": total, "label": label, "url": url}
        if logs is not None:
            state["logs"] = logs
            state["log_version"] += 1

    def apply(selection: set[str]) -> None:
        try:
            on_save(selection, report, cancel_event)
            state["result"] = selection
            state["success"] = True
            current = state["progress"]
            total = max(int(current.get("total", 0)), 1)
            report(total, total, str(current.get("label", "Customization completed")), str(current.get("url", "")))
        except Exception as exc:
            state["result"] = None
            state["error"] = str(exc)
            state["cancelled"] = bool(getattr(exc, "cancelled", False))
            label = "Build cancelled" if state["cancelled"] else "Customization failed"
            report(0 if state["cancelled"] else 1, 1, label, str(state["progress"].get("url", "")))
        finally:
            state["done"] = True
            state["finished_at"] = time.monotonic()

    class Handler(BaseHTTPRequestHandler):
        def _authorized(self) -> bool:
            supplied = parse_qs(urlsplit(self.path).query).get("token", [""])[0]
            return hmac.compare_digest(supplied, token)

        def _reply(self, status: int, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; img-src data:; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'unsafe-inline'; connect-src 'self'; form-action 'self'",
            )
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if not self._authorized():
                self._reply(403, b"Forbidden", "text/plain")
            elif path == "/":
                page = (
                    _render_progress_page(
                        token, can_cancel, page_context=page_context,
                        page_title=page_title, success_title=success_title,
                        initial_label=initial_label,
                        plain_logs=plain_logs,
                    )
                    if start_immediately else _render_page(tools, disabled, title, token, action_label)
                )
                self._reply(200, page)
            elif path == "/status":
                payload = dict(state["progress"])
                payload.update(
                    done=state["done"], success=state["success"],
                    cancelled=state["cancelled"], error=state["error"],
                    logs_ready=bool(state["logs"]),
                    log_version=state["log_version"],
                )
                self._reply(200, json.dumps(payload).encode(), "application/json; charset=utf-8")
                if state["done"] and not state["logs"]:
                    state["reported"] = True
            elif path == "/logs" and state["logs"]:
                self._reply(200, str(state["logs"]).encode(), "text/plain; charset=utf-8")
                if state["done"]:
                    state["reported"] = True
            elif path == "/cancel":
                state["result"] = None
                self._reply(200, _render_result("Selection cancelled", "No changes were applied. You may close this tab.", False))
            else:
                self._reply(404, b"Not found", "text/plain")

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            if not self._authorized():
                self._reply(403, b"Forbidden", "text/plain")
                return
            if path == "/cancel-build" and can_cancel:
                if not state.get("worker_started") or state["done"]:
                    self._reply(409, b"No running build", "text/plain")
                    return
                cancel_event.set()
                current = state["progress"]
                report(
                    int(current.get("completed", 0)), int(current.get("total", 0)),
                    "Cancellation requested", str(current.get("url", "")),
                )
                self._reply(202, b'{"status":"cancelling"}', "application/json; charset=utf-8")
                return
            if path != "/save":
                self._reply(404, b"Not found", "text/plain")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if not 0 <= length <= _MAX_FORM_BYTES:
                self._reply(413, b"Invalid form size", "text/plain")
                return
            form = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))
            selection = _disabled_from_enabled(tools, set(form.get("enabled", [])))
            if on_save is None:
                state["result"] = selection
                self._reply(200, _render_result("Selection saved", "Your tool selection was sent to Nihil. You may close this tab.", True))
            elif state["result"] is not _PENDING or state.get("worker_started"):
                self._reply(409, b"Customization already started", "text/plain")
            else:
                state["worker_started"] = True
                threading.Thread(target=apply, args=(selection,), daemon=True).start()
                self._reply(202, _render_progress_page(token, can_cancel))

        def log_message(self, format: str, *args) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 0.5
    url = f"http://127.0.0.1:{server.server_port}/?{urlencode({'token': token})}"
    print(f"Open {'build progress' if start_immediately else 'the tool selector'}: {url}")
    try:
        webbrowser.open(url)
    except webbrowser.Error:
        pass
    if start_immediately and on_save is not None:
        state["worker_started"] = True
        threading.Thread(target=apply, args=(set(),), daemon=True).start()
    try:
        while state["result"] is _PENDING or (
            on_save is not None and state["done"] and not state["reported"]
            and time.monotonic() - float(state.get("finished_at", 0)) < 10
        ):
            server.handle_request()
    except KeyboardInterrupt:
        print("\nTool selection cancelled.")
        return None
    finally:
        server.server_close()
    if state["error"]:
        raise RuntimeError(str(state["error"]))
    result = state["result"]
    return result if isinstance(result, set) else None
