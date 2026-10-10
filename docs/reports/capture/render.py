"""
Renders the captured evidence as report figures (PNG):
  * HTTP exchanges (exchanges/*.json) in a Postman-style layout: method + URL bar, Body → raw → JSON, response JSON
  * editor views of real evidence files / git versions (VS Code-style)
  * a Collection-Runner view for the filter sweep (PI-19)
The data in every figure is the real captured request/response or the real file content; only the window chrome is drawn.
  python render.py            (renders everything listed below into img/)
"""
import html
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
EX = HERE / "exchanges"
IMG = HERE / "img"
IMG.mkdir(exist_ok=True)
sys.path.insert(0, os.environ.get("PW_LIB", r"C:\Users\rxrat\AppData\Local\Temp\claude\c--Users-rxrat-Documents-Sliit-Y3S2-IRWA-inteliWMS\308fa24e-fed2-4518-8278-89d334a93f85\scratchpad\pwlib"))
from playwright.sync_api import sync_playwright  # noqa: E402

ENV_NAME = {"pi": "IntelliWMS-BEFORE (48d1557)", "rai": "IntelliWMS-BEFORE (26aaed7)", "after": "IntelliWMS-AFTER"}
METHOD_COLOUR = {"GET": "#6bdd9a", "POST": "#ffe47e", "DELETE": "#f79a8e", "PATCH": "#c0a8e1", "PUT": "#74aef6"}
MAX_LINES = 46
SEED_PASSWORDS = {"admin123", "pass123", "pass456", "Test-1234"}

CSS = """
*{box-sizing:border-box} body{margin:0;background:#212121;font-family:'Segoe UI',Inter,Arial,sans-serif;color:#e6e6e6;width:1400px}
.top{display:flex;align-items:center;height:42px;border-bottom:1px solid #353535;background:#1c1c1c}
.tab{display:flex;align-items:center;gap:8px;padding:0 14px;height:42px;border-bottom:2px solid #ff6c37;font-size:13px;max-width:430px;white-space:nowrap;overflow:hidden}
.tab .m{font-weight:700;font-size:11px}.dot{width:7px;height:7px;border-radius:50%;background:#ff6c37}
.plus{color:#9e9e9e;font-size:20px;padding:0 14px}.grow{flex:1}
.env{display:flex;align-items:center;gap:8px;border-left:1px solid #353535;height:42px;padding:0 18px;font-size:13px;color:#e6e6e6}
.env b{color:#fff}.title{display:flex;align-items:center;gap:12px;padding:12px 18px;font-size:15px;font-weight:600}
.badge{border:1px solid #6b6b6b;border-radius:4px;font-size:9px;padding:2px 3px;color:#cfcfcf}
.save{margin-left:auto;display:flex;gap:10px;color:#cfcfcf;font-size:13px;font-weight:400}
.save span{border:1px solid #4a4a4a;border-radius:6px;padding:7px 14px}
.req{display:flex;margin:4px 18px 0 18px;gap:8px}
.urlbox{flex:1;display:flex;border:1px solid #4a4a4a;border-radius:6px;height:46px;align-items:center;background:#262626}
.meth{width:128px;padding-left:14px;font-weight:700;font-size:14px;border-right:1px solid #4a4a4a;height:100%;display:flex;align-items:center;justify-content:space-between;padding-right:12px}
.url{padding-left:16px;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.send{background:#097bed;color:#fff;font-weight:600;border-radius:6px;width:120px;display:flex;align-items:center;justify-content:center;font-size:16px}
.tabs{display:flex;gap:28px;padding:14px 22px 0 22px;font-size:14px;color:#b5b5b5;border-bottom:1px solid #2e2e2e}
.tabs span{padding-bottom:10px}.tabs .on{color:#fff;border-bottom:2px solid #ff6c37}.tabs .g{color:#6bdd9a}.cookies{margin-left:auto;color:#3b9cff}
.radios{display:flex;gap:22px;padding:12px 22px;font-size:14px;color:#e6e6e6;align-items:center}
.r{display:flex;align-items:center;gap:7px}.c{width:15px;height:15px;border:1.5px solid #8a8a8a;border-radius:50%}
.c.on{border:4px solid #3b9cff}.json{color:#3b9cff;font-weight:600}.beaut{margin-left:auto;color:#3b9cff}.schema{color:#bdbdbd}
.code{margin:0 12px 0 12px;border-top:1px solid #2e2e2e;font-family:Consolas,'Courier New',monospace;font-size:13.5px;line-height:21px}
.ln{display:flex}.no{width:54px;text-align:right;padding-right:16px;color:#6f6f6f;flex:none;user-select:none}
.tx{white-space:pre-wrap;word-break:break-all;flex:1;padding-right:14px}
.k{color:#9cdcfe}.s{color:#ce9178}.n{color:#b5cea8}.b{color:#569cd6}.p{color:#d4d4d4}
.respbar{display:flex;align-items:center;gap:14px;padding:12px 20px;border-top:1px solid #353535;margin-top:8px;font-size:14px}
.respbar b{font-size:15px}.stat{margin-left:auto;display:flex;gap:14px;font-size:13px}
.ok{color:#6bdd9a;background:#203528;padding:3px 8px;border-radius:4px}.bad{color:#f79a8e;background:#3a2222;padding:3px 8px;border-radius:4px}
.rtabs{display:flex;gap:24px;padding:0 22px 8px 22px;font-size:13px;color:#b5b5b5}.rtabs .on{color:#fff;border-bottom:2px solid #ff6c37;padding-bottom:6px}
.nobody{padding:18px 26px;color:#9e9e9e;font-size:13px}.note{padding:6px 26px 12px 26px;color:#9e9e9e;font-size:12px;font-style:italic}
.step{padding:10px 20px 4px 20px;color:#ffb07a;font-size:13px;font-weight:600;border-top:3px solid #353535}
.foot{padding:10px 20px;color:#7a7a7a;font-size:11px;border-top:1px solid #2e2e2e}
"""


def _span(cls, text):
    return f'<span class="{cls}">{html.escape(text)}</span>'


def _highlight(value, indent=0, key=None, last=True):
    """Pretty JSON as a list of HTML lines with Postman-like colours."""
    pad = "  " * indent
    head = (_span("k", json.dumps(key, ensure_ascii=False)) + _span("p", ": ")) if key is not None else ""
    comma = "" if last else _span("p", ",")
    if isinstance(value, dict):
        if not value:
            return [pad + head + _span("p", "{}") + comma]
        lines = [pad + head + _span("p", "{")]
        items = list(value.items())
        for i, (k, v) in enumerate(items):
            lines += _highlight(v, indent + 1, k, i == len(items) - 1)
        return lines + ["  " * indent + _span("p", "}") + comma]
    if isinstance(value, list):
        if not value:
            return [pad + head + _span("p", "[]") + comma]
        lines = [pad + head + _span("p", "[")]
        for i, v in enumerate(value):
            lines += _highlight(v, indent + 1, None, i == len(value) - 1)
        return lines + ["  " * indent + _span("p", "]") + comma]
    if isinstance(value, str):
        # Never show real credentials: seed passwords and issued JWTs are masked (deliberately wrong passwords stay visible)
        if key == "password" and value in SEED_PASSWORDS:
            value = "••••••••"
        elif key in ("token", "access_token") and len(value) > 20:
            value = value[:12] + "…<token hidden>"
        tok = _span("s", json.dumps(value, ensure_ascii=False))
    elif isinstance(value, bool) or value is None:
        tok = _span("b", json.dumps(value))
    else:
        tok = _span("n", json.dumps(value))
    return [pad + head + tok + comma]


def _code(lines, limit=MAX_LINES, note_file=None):
    shown = lines[:limit]
    out = "".join(f'<div class="ln"><div class="no">{i}</div><div class="tx">{l}</div></div>' for i, l in enumerate(shown, 1))
    if len(lines) > limit:
        out += f'<div class="note">… {len(lines) - limit} more lines – full response in {note_file}</div>'
    return f'<div class="code">{out}</div>'


def _size(n):
    return f"{n} B" if n < 1024 else f"{n / 1024:.2f} KB"


def _pane(ex, file_name, full_chrome=True, step_label=None, resp_limit=MAX_LINES):
    m = ex["method"]
    colour = METHOD_COLOUR.get(m, "#e6e6e6")
    url = ex["url"].replace("127.0.0.1", "localhost")
    parts = []
    if step_label:
        parts.append(f'<div class="step">{html.escape(step_label)}</div>')
    if full_chrome:
        parts.append(f'<div class="title"><span class="badge">HTTP</span>{html.escape(url)}'
                     f'<div class="save"><span>&#128190; Save</span><span>Share</span></div></div>')
    n_headers = len(ex.get("request_headers") or {}) + 7
    parts.append(f'<div class="req"><div class="urlbox"><div class="meth" style="color:{colour}">{m}<span style="color:#9e9e9e">&#8964;</span></div>'
                 f'<div class="url">{html.escape(url)}</div></div><div class="send">Send</div></div>')
    auth = "Bearer Token" if (ex.get("request_headers") or {}).get("Authorization") else "No Auth"
    parts.append(f'<div class="tabs"><span>&#9776; Docs</span><span>Params</span><span title="{auth}">Authorization</span>'
                 f'<span>Headers <span class="g">({n_headers})</span></span><span class="on">Body <span class="g">&#9679;</span></span>'
                 f'<span>Scripts</span><span>Tests</span><span>Settings</span><span class="cookies">Cookies</span></div>')
    body = ex.get("request_json")
    if body is None:
        parts.append('<div class="radios"><span class="r"><span class="c on"></span>none</span><span class="r"><span class="c"></span>form-data</span>'
                     '<span class="r"><span class="c"></span>x-www-form-urlencoded</span><span class="r"><span class="c"></span>raw</span>'
                     '<span class="r"><span class="c"></span>binary</span><span class="r"><span class="c"></span>GraphQL</span></div>'
                     f'<div class="nobody">This request does not have a body. &nbsp;·&nbsp; Authorization: {auth}</div>')
    else:
        parts.append('<div class="radios"><span class="r"><span class="c"></span>none</span><span class="r"><span class="c"></span>form-data</span>'
                     '<span class="r"><span class="c"></span>x-www-form-urlencoded</span><span class="r"><span class="c on"></span>raw</span>'
                     '<span class="r"><span class="c"></span>binary</span><span class="r"><span class="c"></span>GraphQL</span>'
                     '<span class="json">JSON &#8964;</span><span class="beaut"><span class="schema">&#9881; Schema</span> &nbsp; Beautify</span></div>')
        parts.append(_code(_highlight(body), limit=18, note_file=file_name))
    good = 200 <= ex["status"] < 300
    st = f'<span class="{"ok" if good else "bad"}">{ex["status"]} {html.escape(ex.get("reason") or "")}</span>'
    parts.append(f'<div class="respbar"><b>Response</b><span style="color:#9e9e9e">&#8634;</span><div class="stat">{st}'
                 f'<span>{ex["ms"]} ms</span><span>{_size(ex["size"])}</span></div></div>')
    parts.append('<div class="rtabs"><span class="on">Body</span><span>Cookies</span><span>Headers</span><span>Test Results</span>'
                 '<span style="margin-left:auto">{ } JSON &#8964; &nbsp; Preview &nbsp; Visualize</span></div>')
    rj = ex.get("response_json")
    if rj is None:
        text = ex.get("response_text") or ""
        parts.append('<div class="nobody">' + (html.escape(text[:600]) if text else "No response body (" + str(ex["status"]) + ").") + '</div>')
    else:
        parts.append(_code(_highlight(rj), limit=resp_limit, note_file=file_name))
    return "".join(parts)


def _chrome(env, ex, inner):
    m = ex["method"]
    url = ex["url"].replace("127.0.0.1", "localhost")
    return (f'<div class="top"><div class="tab"><span class="m" style="color:{METHOD_COLOUR.get(m)}">{m}</span>'
            f'{html.escape(url[:46])}<span class="dot"></span></div><span class="plus">+</span><span class="grow"></span>'
            f'<div class="env">&#127760; Environment: <b>{html.escape(env)}</b></div></div>{inner}')


def exchange_html(path, step=None, run=0):
    data = json.loads(path.read_text(encoding="utf-8"))
    env = ENV_NAME[data["stack"]]
    steps = data["runs"][run]
    rel = "docs/reports/capture/exchanges/" + path.name
    total = len(steps)
    if step is not None:
        steps = [steps[step]]
    if len(steps) == 1:
        inner = _pane(steps[0], rel, step_label=f"Request {step + 1} of {total}" if step is not None and total > 1 else None)
    else:
        limit = 22 if len(steps) <= 2 else 14
        inner = "".join(_pane(ex, rel, full_chrome=(i == 0), resp_limit=limit,
                              step_label=f"Request {i + 1} of {len(steps)}") for i, ex in enumerate(steps))
    runs_note = f" · run {run + 1} of {len(data['runs'])}" if len(data["runs"]) > 1 else ""
    foot = (f'<div class="foot">Captured {steps[-1]["sent_at"]} by the evidence harness (docs/reports/capture/run_live.py){runs_note} – '
            f'request and response exactly as exchanged; token hidden.</div>')
    return _chrome(env, steps[0], inner) + foot


def runner_html(path, title):
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = ""
    blocked = 0
    for i, ex in enumerate(data["runs"][0], 1):
        rj = ex["response_json"] or {}
        inj = rj.get("is_injection")
        blocked += bool(inj)
        reason = rj.get("reason") or ""
        rule = reason.split("rule:")[-1].strip(" )") if "rule:" in reason else "–"
        rows += (f'<tr><td>{i}</td><td><span style="color:{METHOD_COLOUR["POST"]};font-weight:700">POST</span> /security/test-injection</td>'
                 f'<td style="font-family:Consolas">{html.escape(ex["request_json"]["text"])}</td><td><span class="ok">200 OK</span></td>'
                 f'<td style="color:{"#6bdd9a" if inj else "#f79a8e"};font-weight:700">{json.dumps(inj)}</td><td>{html.escape(rule)}</td><td>{ex["ms"]} ms</td></tr>')
    env = ENV_NAME[data["stack"]]
    return (f'<div class="top"><div class="tab"><span class="m" style="color:#ff6c37">RUN</span>{html.escape(title)}</div><span class="grow"></span>'
            f'<div class="env">&#127760; Environment: <b>{html.escape(env)}</b></div></div>'
            f'<div class="title">Collection Runner – PI-19 filter sweep &nbsp;<span class="save"><span>Iterations: {len(data["runs"][0])}</span>'
            f'<span>Blocked (is_injection = true): {blocked} / {len(data["runs"][0])}</span></span></div>'
            '<style>table{border-collapse:collapse;width:1360px;margin:6px 20px 14px 20px;font-size:13.5px}'
            'th,td{border-bottom:1px solid #353535;padding:9px 10px;text-align:left}th{color:#9e9e9e;font-weight:600}</style>'
            '<table><tr><th>#</th><th>Request</th><th>Body: text</th><th>Status</th><th>is_injection</th><th>Rule</th><th>Time</th></tr>'
            f'{rows}</table><div class="foot">Captured {data["runs"][0][-1]["sent_at"]} by docs/reports/capture/run_live.py – one request per variant.</div>')


EDITOR_CSS = """
.ed{background:#1e1e1e;width:1400px}.edtop{background:#252526;display:flex;font-size:13px;color:#cccccc}
.edtab{background:#1e1e1e;padding:9px 16px;border-top:1px solid #0e7ad3;color:#fff}.crumb{padding:6px 18px;color:#a0a0a0;font-size:12.5px;background:#1e1e1e;border-bottom:1px solid #2b2b2b}
.hl{background:#3a3d41}
"""


def editor_html(title, crumb, lines, start, highlight=()):
    body = ""
    for i, line in enumerate(lines, start):
        cls = ' class="ln hl"' if any(h in line for h in highlight) else ' class="ln"'
        body += f'<div{cls}><div class="no">{i}</div><div class="tx">{html.escape(line)}</div></div>'
    return (f'<div class="ed"><div class="edtop"><div class="edtab">{html.escape(title)}</div></div>'
            f'<div class="crumb">{html.escape(crumb)}</div><div class="code" style="margin:0;border:0;padding:6px 0">{body}</div></div>')


def file_lines(spec):
    """(title, crumb, lines, first_line_no) for a file or a git version, windowed around a search string"""
    if spec.get("git"):
        text = subprocess.run(["git", "show", spec["git"]], cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout
        title, crumb = spec["git"].split(":")[-1].split("/")[-1], f"git show {spec['git']}"
    else:
        text = (REPO / spec["path"]).read_text(encoding="utf-8")
        title, crumb = Path(spec["path"]).name, spec["path"].replace("/", " › ")
    lines = text.splitlines()
    at = 0
    if spec.get("find"):
        at = next((i for i, l in enumerate(lines) if spec["find"] in l), 0)
    before, after = spec.get("before", 6), spec.get("after", 26)
    s = max(0, at - before)
    return title, crumb, [l[:220] for l in lines[s:at + after]], s + 1


FILE_FIGS = {
    "PI-04#1": {"git": "48d1557:config/llm_config.py", "find": "full_prompt = f", "hl": ["full_prompt", "contents=full_prompt"], "before": 14, "after": 16},
    "PI-11#1": {"path": "docs/reports/evidence/normalizer_check_results.json", "find": "{", "hl": ["accepted", "rejected_unsafe"], "before": 0, "after": 20},
    "RA-01#1": {"path": "audit/hallucination_2026-10-07/H01_evidence.json", "find": '"response_text"', "hl": ['"response_text"', '"number"'], "before": 2, "after": 30},
    "RA-02#1": {"path": "audit/hallucination_2026-10-07/H02_evidence.json", "find": '"response_text"', "hl": ['"response_text"'], "before": 4, "after": 14},
    "RA-03#1": {"path": "audit/hallucination_2026-10-07/H03_evidence.json", "find": '"response_text"', "hl": ['"response_text"'], "before": 4, "after": 14},
    "RA-12#1": {"path": "audit/bias_2026-10-07/runs.json", "find": '"response_text"', "hl": ['"response_text"', '"orientation"', '"prompt"'], "before": 22, "after": 6},
    "RA-14#1": {"path": "docs/reports/evidence/rai_before_26aaed7.json", "find": '"RAI-15.names"', "hl": ["Gates", "All ", "Search", "Many"], "before": 1, "after": 26},
    "RA-17#1": {"path": "audit/toxicity_2026-10-07/T01.json", "find": '"response"', "hl": ['"response"', '"query"'], "before": 6, "after": 10},
    "RA-20#1": {"path": "audit/fairness_2026-10-07/F01-base.json", "find": '"response"', "hl": ['"response"'], "before": 4, "after": 10},
    "RA-21#1": {"path": "audit/fairness_2026-10-07/F02.json", "find": "160", "hl": ["160"], "before": 6, "after": 22},
    "RA-23#1": {"git": "26aaed71adc644cd29b8fbccc5d9d5054bbc654f:agents/inventory_agent/anomaly_watcher.py", "find": "OP-882", "hl": ["OP-882"], "before": 12, "after": 6},
    "RA-24#1": {"path": "audit/transparency_2026-10-07/TR01.json", "find": '"response"', "hl": ['"response"', "MCP_TIMEOUT"], "before": 4, "after": 12},
    "RA-25#1": {"path": "audit/transparency_2026-10-07/TR02.json", "find": '"response"', "hl": ['"response"'], "before": 4, "after": 12},
    "RA-27#1": {"path": "audit/explainability_2026-10-07/E01.json", "find": '"response"', "hl": ['"response"'], "before": 4, "after": 12},
    "RA-30#1": {"path": "audit/harmful_content_2026-10-07/HC01.json", "find": '"response"', "hl": ['"response"'], "before": 4, "after": 12},
    "RA-31#1": {"path": "audit/harmful_content_2026-10-07/HC02.json", "find": '"response"', "hl": ['"response"', "can be picked now"], "before": 4, "after": 12},
    "RA-36#2": {"path": "frontend/src/twin/KnowledgeCampusTwin.jsx", "find": "Live", "hl": ["Live"], "before": 8, "after": 16},
}

# figure key → (exchange file, optional step index)
EXCHANGE_FIGS = {
    "RA-23#3": ("RA-23_B.json", None),
}
RUNNER_FIGS = {"PI-19#1": "PI-19_1.json", "PI-19#2": "PI-19_2.json"}


def page_png(pg, body_html, out):
    pg.set_content(f"<html><head><meta charset='utf-8'><style>{CSS}{EDITOR_CSS}</style></head><body>{body_html}</body></html>")
    pg.wait_for_timeout(50)
    pg.screenshot(path=str(out), full_page=True)


def main(only=None):
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1400, "height": 300}, device_scale_factor=1)
        done = 0
        for f in sorted(EX.glob("*.json")):
            key = f.stem.replace("_", "#", 1) if f.stem.count("_") == 1 else f.stem
            key = f.stem[: f.stem.rfind("_")] + "#" + f.stem[f.stem.rfind("_") + 1:]
            if key in RUNNER_FIGS or key == "RA-23#B":
                continue
            if only and not key.startswith(only):
                continue
            out = IMG / f"fig_{key.replace('#', '_')}.png"
            page_png(pg, exchange_html(f), out)
            done += 1
            # 3+ requests in one figure become unreadable when scaled to a page: also save one image per request
            for old in IMG.glob(out.stem + "_p*.png"):
                old.unlink()
            n_steps = len(json.loads(f.read_text(encoding="utf-8"))["runs"][0])
            if n_steps > 2:
                for i in range(n_steps):
                    page_png(pg, exchange_html(f, i), IMG / f"{out.stem}_p{i + 1}.png")
        for key, fname in RUNNER_FIGS.items():
            if not only or key.startswith(only):
                page_png(pg, runner_html(EX / fname, "IntelliWMS – filter sweep"), IMG / f"fig_{key.replace('#', '_')}.png")
                done += 1
        for key, (fname, step) in EXCHANGE_FIGS.items():
            if not only or key.startswith(only):
                page_png(pg, exchange_html(EX / fname, step), IMG / f"fig_{key.replace('#', '_')}.png")
                done += 1
        for key, spec in FILE_FIGS.items():
            if only and not key.startswith(only):
                continue
            title, crumb, lines, start = file_lines(spec)
            page_png(pg, editor_html(title, crumb, lines, start, spec.get("hl", ())), IMG / f"fig_{key.replace('#', '_')}.png")
            done += 1
        b.close()
    print("rendered", done)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
