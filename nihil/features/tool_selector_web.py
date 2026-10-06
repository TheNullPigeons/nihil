#!/usr/bin/env python3
"""Local browser UI for selecting tools in a custom Nihil image."""

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
:root {{ color-scheme:dark; font-family:'Plus Jakarta Sans',ui-sans-serif,system-ui,sans-serif; background:#000; color:#f8fafc }}
* {{ box-sizing:border-box }} body {{ display:grid; min-height:100vh; margin:0; place-items:center; background:#000 }}
.card {{ width:min(440px,calc(100% - 32px)); padding:42px; border:1px solid #334155cc; border-radius:20px; background:#0f172a80; text-align:center; box-shadow:0 24px 70px #020617b3 }}
.icon {{ display:grid; width:58px; height:58px; margin:0 auto 22px; place-items:center; border-radius:16px; font-size:30px; font-weight:800 }}
.success {{ border:1px solid #34d39955; background:#10b98118; color:#34d399 }} .cancelled {{ border:1px solid #f59e0b55; background:#f59e0b18; color:#fbbf24 }}
h1 {{ margin:0 0 10px; font-size:27px; letter-spacing:-.03em }} p {{ margin:0; color:#94a3b8; line-height:1.6 }}
.brand {{ margin-top:28px; color:#64748b; font-size:11px; letter-spacing:.14em; text-transform:uppercase }} .brand b {{ color:#fbbf24 }}
</style></head><body><main class="card"><div class="icon {tone}">{icon}</div><h1>{html.escape(title)}</h1>
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
:root {{ color-scheme:dark; font-family:'Plus Jakarta Sans',ui-sans-serif,system-ui,sans-serif; background:#000; color:#f8fafc; accent-color:#f59e0b }}
* {{ box-sizing:border-box }} body {{ margin:0; min-height:100vh; background:#000 }}
.site-head {{ position:sticky; top:0; z-index:4; border-bottom:1px solid #1e293bcc; background:#000000d9; backdrop-filter:blur(16px) }}
.site-head-inner {{ display:flex; align-items:center; justify-content:space-between; width:min(1180px,calc(100% - 32px)); height:66px; margin:auto }}
.brand {{ display:flex; align-items:center; gap:12px }} .brand-copy {{ display:flex; flex-direction:column; line-height:1.25 }} .brand-copy strong {{ font-size:15px }} .brand-copy small {{ color:#94a3b8; font-size:11px }}
.brand-mark {{ display:grid; place-items:center; width:40px; height:40px; border:1px solid #334155; border-radius:10px; background:#0f172acc; color:#fbbf24; font-size:19px; font-weight:800; box-shadow:0 0 20px #f59e0b14 }}
.local-badge {{ display:flex; align-items:center; gap:7px; padding:7px 11px; border:1px solid #334155; border-radius:999px; background:#0f172acc; color:#94a3b8; font-size:11px }} .local-badge:before {{ content:''; width:6px; height:6px; border-radius:50%; background:#34d399; box-shadow:0 0 8px #34d399 }}
.page {{ width:min(1180px,calc(100% - 32px)); margin:auto; padding:46px 0 112px }}
.hero {{ display:flex; justify-content:space-between; align-items:end; gap:24px; margin:0 0 32px }}
h1 {{ margin:0 0 8px; font-size:clamp(30px,5vw,48px); letter-spacing:-.04em }} .subtitle {{ color:#94a3b8 }}
.stats {{ display:flex; gap:8px; flex-wrap:wrap }} .stat {{ min-width:92px; padding:10px 14px; border:1px solid #334155cc; border-radius:12px; background:#0f172a80 }}
.stat b {{ display:block; color:#fbbf24; font-size:20px }} .stat small {{ color:#64748b; font-size:11px; text-transform:uppercase; letter-spacing:.08em }}
.filters {{ position:sticky; top:78px; z-index:2; display:grid; grid-template-columns:minmax(220px,1fr) 180px 170px auto; gap:10px; padding:12px; border:1px solid #334155cc; border-radius:14px; background:#0f172aeF; box-shadow:0 12px 30px #02061773; backdrop-filter:blur(12px) }}
input[type=search],select {{ width:100%; min-height:42px; border:1px solid #475569; border-radius:9px; padding:0 12px; background:#020617; color:#e2e8f0; font:inherit; outline:none }}
input[type=search]:focus,select:focus {{ border-color:#f59e0b; box-shadow:0 0 0 3px #f59e0b20 }}
.toggle-buttons {{ display:flex; gap:6px }} button,.cancel {{ border:1px solid #475569; border-radius:9px; padding:10px 14px; background:#1e293b; color:#e2e8f0; cursor:pointer; text-decoration:none; font:inherit; font-size:13px; font-weight:600; white-space:nowrap }}
button:hover,.cancel:hover {{ border-color:#64748b; background:#334155 }}
.group {{ margin-top:26px }} .group-head {{ display:flex; align-items:center; justify-content:space-between; margin:0 2px 10px }}
.category-toggle {{ display:flex; align-items:center; gap:9px; cursor:pointer }} .category-toggle input {{ position:absolute; opacity:0 }} .category-check {{ display:grid; place-items:center; width:17px; height:17px; border:1px solid #64748b; border-radius:5px; background:#0f172a }}
.category-toggle input:checked + .category-check {{ border-color:#f59e0b; background:#f59e0b }} .category-toggle input:checked + .category-check:after {{ content:'✓'; color:#0f172a; font-size:12px; font-weight:900 }} .category-toggle input:indeterminate + .category-check {{ border-color:#f59e0b; background:#f59e0b }} .category-toggle input:indeterminate + .category-check:after {{ content:'−'; color:#0f172a; font-weight:900 }}
.group h2 {{ margin:0; color:#e2e8f0; font-size:13px; letter-spacing:.12em; text-transform:uppercase }} .group-count {{ color:#64748b; font:12px ui-monospace,monospace }}
.tool-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px }}
.tool {{ position:relative; display:flex; align-items:center; gap:12px; min-width:0; padding:14px; border:1px solid #334155cc; border-radius:12px; background:#0f172a80; cursor:pointer; transition:border-color .15s,background .15s,transform .15s }}
.tool:hover {{ border-color:#64748b; background:#0f172ab3; transform:translateY(-1px) }} .tool:has(input:checked) {{ border-color:#f59e0b4d; background:linear-gradient(135deg,#f59e0b12,#0f172a80 70%) }}
.tool input {{ position:absolute; opacity:0; pointer-events:none }} .checkmark {{ flex:none; width:20px; height:20px; border:1px solid #64748b; border-radius:6px }}
.tool input:checked + .checkmark {{ border-color:#f59e0b; background:#f59e0b }} .tool input:checked + .checkmark:after {{ content:'✓'; display:block; color:#09090b; text-align:center; font-weight:900; line-height:18px }}
.tool-copy {{ min-width:0; display:flex; flex:1; flex-direction:column; gap:4px }} .tool-copy b {{ overflow:hidden; text-overflow:ellipsis; font-size:14px }} code {{ overflow:hidden; color:#64748b; font-size:11px; text-overflow:ellipsis }}
.required {{ align-self:flex-start; color:#fbbf24; font:9px ui-monospace,monospace; letter-spacing:.08em; text-transform:uppercase }} .tool:has(input:disabled) {{ cursor:default }}
.actions {{ position:fixed; z-index:3; right:0; bottom:0; left:0; border-top:1px solid #1e293b; background:#000000eb; backdrop-filter:blur(16px) }} .actions-inner {{ display:flex; align-items:center; justify-content:space-between; width:min(1180px,calc(100% - 32px)); margin:auto; padding:14px 0 }}
.selection {{ color:#94a3b8; font-size:13px }} .selection strong {{ color:#fbbf24 }} .action-buttons {{ display:flex; gap:8px }} button.primary {{ border-color:#f59e0b; background:#f59e0b; color:#0f172a; font-weight:800; box-shadow:0 8px 24px #f59e0b1f }} button.primary:hover {{ background:#fbbf24 }}
.hidden {{ display:none }} .empty {{ display:none; padding:70px 20px; color:#64748b; text-align:center }} .empty.visible {{ display:block }}
@media(max-width:850px) {{ .hero {{ align-items:start; flex-direction:column }} .filters {{ grid-template-columns:1fr 1fr }} .filters input {{ grid-column:1/-1 }} .tool-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)) }} }}
@media(max-width:540px) {{ .page {{ width:min(100% - 20px,1180px); padding-top:24px }} .filters,.tool-grid {{ grid-template-columns:1fr }} .filters select,.toggle-buttons {{ grid-column:1 }} .toggle-buttons button {{ flex:1 }} .stats {{ width:100% }} .stat {{ flex:1 }} .selection {{ display:none }} }}
</style></head><body>
<header class="site-head"><div class="site-head-inner"><div class="brand"><span class="brand-mark">N</span><span class="brand-copy"><strong>TheNullPigeons</strong><small>Nihil image customizer</small></span></div><span class="local-badge">Local session</span></div></header>
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


def _render_progress_page(token: str, can_cancel: bool = False) -> bytes:
    status_url = "/status?" + urlencode({"token": token})
    logs_url = "/logs?" + urlencode({"token": token})
    cancel_url = "/cancel-build?" + urlencode({"token": token})
    cancel_button = '<button id="cancel-build" type="button">Cancel build</button>' if can_cancel else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Nihil customization</title><style>
:root {{ color-scheme:dark; font-family:'Plus Jakarta Sans',ui-sans-serif,system-ui,sans-serif; background:#000; color:#f8fafc }}
* {{ box-sizing:border-box }} body {{ min-height:100vh; margin:0; padding:32px 16px; background:#000 }}
.card {{ width:min(1400px,100%); margin:0 auto; padding:42px; border:1px solid #334155cc; border-radius:20px; background:#0f172a80; box-shadow:0 24px 70px #020617b3 }} .summary {{ width:min(680px,100%); margin:0 auto }}
.eyebrow {{ display:flex; align-items:center; gap:8px; color:#fbbf24; font-size:11px; font-weight:700; letter-spacing:.14em; text-transform:uppercase }} .pulse {{ width:7px; height:7px; border-radius:50%; background:#34d399; box-shadow:0 0 0 0 #34d39988; animation:pulse 1.5s infinite }} h1 {{ margin:10px 0 8px; font-size:30px; letter-spacing:-.03em }}
#label,#detail {{ color:#94a3b8 }} #label.changed {{ animation:step-change .4s ease }} .progress-track {{ width:100%; height:12px; margin:28px 0 12px; overflow:hidden; border-radius:999px; background:#1e293b }} .progress-fill {{ width:0; height:100%; border-radius:inherit; background:linear-gradient(90deg,#d97706,#fbbf24,#f59e0b); background-size:200% 100%; box-shadow:0 0 18px #f59e0b66; transition:width .7s cubic-bezier(.22,1,.36,1); animation:shimmer 1.4s linear infinite }} .progress-track.indeterminate .progress-fill {{ width:35%; animation:indeterminate 1.25s ease-in-out infinite,shimmer 1.4s linear infinite }}
.meta {{ display:flex; justify-content:space-between; gap:16px; color:#64748b; font:12px ui-monospace,monospace }}
a {{ display:none; margin-top:24px; color:#fbbf24 }} a.has-run {{ display:inline-block }} button {{ float:right; margin-top:18px; padding:9px 13px; border:1px solid #ef444466; border-radius:9px; background:#ef444414; color:#fca5a5; cursor:pointer }} button:disabled {{ cursor:default; opacity:.55 }} .done button {{ display:none }} .done .pulse {{ animation:none }} .failed .eyebrow {{ color:#f87171 }} .failed .progress-fill {{ background:#ef4444 }}
.logs {{ display:none; clear:both; margin-top:30px; padding-top:24px; border-top:1px solid #334155 }} .has-logs .logs {{ display:block }} .logs-head {{ display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:10px }} .logs h2 {{ margin:0; font-size:14px }} .logs a {{ display:inline; margin:0; font-size:12px }} pre {{ width:100%; height:70vh; min-height:520px; margin:0; padding:18px; overflow:auto; border:1px solid #334155; border-radius:12px; background:#020617; color:#cbd5e1; font:12px/1.55 ui-monospace,monospace; white-space:pre; tab-size:2 }}
.log-line {{ display:block }} .log-job {{ color:#38bdf8 }} .log-step {{ color:#c084fc }} .log-time {{ color:#64748b }} .log-error {{ color:#f87171 }} .log-warning {{ color:#fbbf24 }} .log-success {{ color:#34d399 }}
@keyframes pulse {{ 70% {{ box-shadow:0 0 0 8px #34d39900 }} 100% {{ box-shadow:0 0 0 0 #34d39900 }} }} @keyframes shimmer {{ to {{ background-position:-200% 0 }} }} @keyframes indeterminate {{ from {{ transform:translateX(-120%) }} to {{ transform:translateX(330%) }} }} @keyframes step-change {{ 50% {{ color:#fbbf24; transform:translateX(4px) }} }}
@media(prefers-reduced-motion:reduce) {{ .pulse,.progress-fill,.progress-track.indeterminate .progress-fill,#label.changed {{ animation:none }} .progress-fill {{ transition:none }} }}
</style></head><body><main id="card" class="card"><div class="summary"><div class="eyebrow"><span class="pulse"></span>Nihil · GitHub Actions</div><h1 id="title">Building your image…</h1>
<p id="label">Preparing customization</p><div id="bar" class="progress-track indeterminate" role="progressbar" aria-label="Build progress"><div class="progress-fill"></div></div><div class="meta"><span id="detail">Starting…</span><span><span id="elapsed">00:00</span> · <span id="percent">waiting</span></span></div>
<a id="run" target="_blank" rel="noreferrer">View live logs on GitHub →</a>{cancel_button}</div><section class="logs"><div class="logs-head"><h2>Complete build logs</h2><a id="download" download="nihil-build.log">Download logs</a></div><pre id="logs"></pre></section></main>
<script>
const card=document.querySelector('#card'),bar=document.querySelector('#bar'),fill=bar.querySelector('.progress-fill'),label=document.querySelector('#label'),detail=document.querySelector('#detail'),percent=document.querySelector('#percent'),elapsed=document.querySelector('#elapsed'),run=document.querySelector('#run'),cancel=document.querySelector('#cancel-build'),logs=document.querySelector('#logs'),download=document.querySelector('#download'),started=Date.now();let lastLabel='';
const clock=setInterval(()=>{{const seconds=Math.floor((Date.now()-started)/1000);elapsed.textContent=String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0')}},1000);
if(cancel)cancel.addEventListener('click',async()=>{{cancel.disabled=true;cancel.textContent='Cancellation requested…';await fetch('{cancel_url}',{{method:'POST'}})}});
function renderLogs(text){{const fragment=document.createDocumentFragment();for(const line of text.split('\\n')){{const row=document.createElement('span');row.className='log-line';const parts=line.split('\\t');const message=parts.length>3?parts.slice(3).join('\\t'):line;if(parts.length>3){{for(const [value,className] of [[parts[0],'log-job'],[parts[1],'log-step'],[parts[2],'log-time']]){{const part=document.createElement('span');part.className=className;part.textContent=value;row.append(part,document.createTextNode('\\t'))}}}}const content=document.createElement('span');content.textContent=message;if(/\\b(error|failed|failure|fatal)\\b/i.test(message))content.className='log-error';else if(/\\b(warn|warning)\\b/i.test(message))content.className='log-warning';else if(/\\b(success|succeeded|complete|completed|passed)\\b/i.test(message))content.className='log-success';row.append(content);fragment.append(row)}}logs.replaceChildren(fragment)}}
async function poll(){{try{{const response=await fetch('{status_url}',{{cache:'no-store'}});const state=await response.json();if(state.label!==lastLabel){{lastLabel=state.label;label.textContent=state.label;label.classList.remove('changed');void label.offsetWidth;label.classList.add('changed')}}if(state.total>0){{const value=Math.round(state.completed/state.total*100);bar.classList.remove('indeterminate');fill.style.width=value+'%';bar.setAttribute('aria-valuenow',value);percent.textContent=value+'%';detail.textContent=state.completed+' / '+state.total+' steps'}}else{{bar.classList.add('indeterminate');fill.style.width='';bar.removeAttribute('aria-valuenow');percent.textContent='waiting';detail.textContent='GitHub is working…'}}if(state.url){{run.href=state.url;run.classList.add('has-run')}}if(state.done){{clearInterval(clock);card.classList.add('done');document.querySelector('#title').textContent=state.success?'Customization complete':state.cancelled?'Build cancelled':'Build failed';if(state.success)fill.style.width='100%';if(!state.success&&!state.cancelled)card.classList.add('failed');detail.textContent=state.success?'Build complete. Loading logs…':state.error;if(state.logs_ready){{const response=await fetch('{logs_url}',{{cache:'no-store'}});if(!response.ok)throw new Error('Complete logs are unavailable');const text=await response.text();renderLogs(text);download.href=URL.createObjectURL(new Blob([text],{{type:'text/plain'}}));card.classList.add('has-logs');detail.textContent='Complete logs are displayed below.'}}return}}}}catch(error){{label.textContent='Connection to Nihil lost';detail.textContent=error}}setTimeout(poll,1000)}}poll();
</script></body></html>""".encode()


def select_tools_web(
    tools: list[dict], disabled: set[str], title: str, *, on_save=None,
    action_label: str = "Apply selection", can_cancel: bool = False,
) -> set[str] | None:
    """Open a one-session localhost selector and wait for save or cancel."""
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
    }
    cancel_event = threading.Event()

    def report(
        completed: int, total: int, label: str, url: str = "", logs: str | None = None,
    ) -> None:
        state["progress"] = {"completed": completed, "total": total, "label": label, "url": url}
        if logs is not None:
            state["logs"] = logs

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
            report(1, 1, label, str(state["progress"].get("url", "")))
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
                "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; form-action 'self'",
            )
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if not self._authorized():
                self._reply(403, b"Forbidden", "text/plain")
            elif path == "/":
                self._reply(200, _render_page(tools, disabled, title, token, action_label))
            elif path == "/status":
                payload = dict(state["progress"])
                payload.update(
                    done=state["done"], success=state["success"],
                    cancelled=state["cancelled"], error=state["error"],
                    logs_ready=bool(state["logs"]),
                )
                self._reply(200, json.dumps(payload).encode(), "application/json; charset=utf-8")
                if state["done"] and not state["logs"]:
                    state["reported"] = True
            elif path == "/logs" and state["done"] and state["logs"]:
                self._reply(200, str(state["logs"]).encode(), "text/plain; charset=utf-8")
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
    print(f"Open the tool selector: {url}")
    try:
        webbrowser.open(url)
    except webbrowser.Error:
        pass
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
