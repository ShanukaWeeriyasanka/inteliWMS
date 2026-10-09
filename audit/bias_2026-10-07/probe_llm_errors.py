"""
Probe: are the classify-call failures on the no-SKU prompts linked to the label, or to timing?

Sends the exact prompt the coordinator's classifier builds (COORDINATOR_SYSTEM_PROMPT, empty
history, the user query) straight to the same client and model, B01 and B02 interleaved, and
records the full error text (HTTP status and provider message) that the app's log leaves out.
Read-only: no code, prompt, data or setting is changed.

Run from the repository root:
    venv\\Scripts\\python audit\\bias_2026-10-07\\probe_llm_errors.py
"""
import datetime
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from agents.coordinator.intent_classifier import IntentClassifier  # noqa: E402
from config.llm_config import llm_config  # noqa: E402
from config.prompts import COORDINATOR_SYSTEM_PROMPT  # noqa: E402
from run_bias_audit import FORMS, TESTS  # noqa: E402

ROUNDS = 2


def prompt_for(query):
    return f"""{COORDINATOR_SYSTEM_PROMPT}
{IntentClassifier._history_block(None)}
User warehouse query: "{query}"

Analyze the query and return ONLY a valid JSON object:
"""


def main():
    client = llm_config.get_client()
    order = []
    for _ in range(ROUNDS):
        for orientation in ("initial", "swapped"):
            for test_id in ("B01", "B02"):
                first, second = TESTS[test_id]["labels"]
                labels = {"a": first, "b": second} if orientation == "initial" else {"a": second, "b": first}
                order.append((test_id, orientation, FORMS["plain"].format(**labels)))
    results = []
    for i, (test_id, orientation, query) in enumerate(order, 1):
        started = time.perf_counter()
        row = {"n": i, "test": test_id, "orientation": orientation, "model": llm_config.GEMINI_MODEL,
               "sent_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "query": query}
        try:
            response = client.models.generate_content(model=llm_config.GEMINI_MODEL, contents=prompt_for(query))
            row.update(outcome="ok", text=str(getattr(response, "text", "") or ""))
            cand = (getattr(response, "candidates", None) or [None])[0]
            row["finish_reason"] = str(getattr(cand, "finish_reason", None))
        except Exception as exc:
            row.update(outcome="error", error_type=type(exc).__name__,
                       status_code=getattr(exc, "code", None) or getattr(exc, "status_code", None),
                       error=str(exc)[:600])
        row["duration_s"] = round(time.perf_counter() - started, 1)
        results.append(row)
        print(f"{i:2d} {test_id} {orientation:7s} {row['outcome']:5s} {row.get('status_code') or ''} "
              f"{row['duration_s']}s {(row.get('error') or row.get('text') or '')[:160]!r}")
    (HERE / "probe_llm_errors.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saved {len(results)} probes")


if __name__ == "__main__":
    main()
