"""
Supplementary run: the "plain" (no-SKU) B01/B02 pairs with the LLM actually answering.

In the live runs (run_bias_audit.py) every LLM call failed: the provider answered in about
30 s but the app allows 8 s (settings.LLM_TIMEOUT_S), so routing fell back to a fixed reply.
This script runs the SAME prompts through the SAME FastAPI app, in-process (TestClient), with
one difference: LLM_TIMEOUT_S is raised to 90 s inside this Python process only. No code,
configuration file, prompt, model or server setting is changed.

Run from the repository root:
    venv\\Scripts\\python audit\\bias_2026-10-07\\run_bias_llm_path.py
"""
import concurrent.futures
import datetime
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from config.settings import settings  # noqa: E402

settings.LLM_TIMEOUT_S = 90  # this process only

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from run_bias_audit import ATTRIBUTE_WORDS, FORMS, PASSWORD, REPEATS, TESTS, USER, log_lines, recommendation, tool_calls  # noqa: E402


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def one(job):
    test_id, test, orientation, labels, groups, rep, headers = job
    prompt = FORMS["plain"].format(**labels)
    with TestClient(app) as client:
        res = client.post("/query", json={"message": prompt}, headers=headers)
    body = res.json()
    routing = body.get("routing") or {}
    text = body.get("response") or body.get("message") or ""
    lines = log_lines(body.get("trace_id"))
    return {
        "test": test_id, "attribute": test["attribute"], "form": "plain (LLM timeout 90 s, in-process)",
        "orientation": orientation, "repeat": rep, "sent_at": now(), "prompt": prompt,
        "groups_by_supplier": groups, "http_status": res.status_code,
        "thread_id": body.get("thread_id"), "request_id": body.get("request_id"), "trace_id": body.get("trace_id"),
        "agent_used": body.get("agent_used"), "status": body.get("status"),
        "routing": {k: routing.get(k) for k in ("rule_id", "decided_by", "llm_consulted", "llm_status", "domain",
                                                 "confidence", "normalized_query", "reasoning")},
        "decisions": [(d.get("stage"), d.get("outcome"), d.get("rule_id"), d.get("decided_by"), d.get("llm_status"))
                      for d in routing.get("decisions", [])],
        "inventory": {k: (body.get("inventory_details") or {}).get(k) for k in ("sub_intent", "outcome", "source")},
        "response_text": text,
        "tool_and_llm_calls": tool_calls(lines),
        "attribute_words_in_response": sorted({m.lower() for m in ATTRIBUTE_WORDS.findall(text)}),
        "recommendation": recommendation(text, groups),
    }


def main():
    with TestClient(app) as client:
        token = client.post("/auth/login", json={"username": USER, "password": PASSWORD, "role": "staff"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    jobs = []
    for test_id, test in TESTS.items():
        first, second = test["labels"]
        g1, g2 = test["groups"]
        for orientation, labels, groups in (("initial", {"a": first, "b": second}, {"Northbay": g1, "Eastgate": g2}),
                                            ("swapped", {"a": second, "b": first}, {"Northbay": g2, "Eastgate": g1})):
            for rep in range(1, REPEATS + 1):
                jobs.append((test_id, test, orientation, labels, groups, rep, headers))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        runs = list(pool.map(one, jobs))
    for r in runs:
        print(f"{r['test']} {r['orientation']:7s} #{r['repeat']}: agent={r['agent_used']} route={r['routing']['rule_id']} "
              f"by={r['routing']['decided_by']} llm={r['routing']['llm_status']} pick={r['recommendation']['recommended']}")
    (HERE / "runs_llm_path.json").write_text(json.dumps(runs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saved {len(runs)} runs")


if __name__ == "__main__":
    main()
