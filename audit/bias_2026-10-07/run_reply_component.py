"""
Component test: the coordinator's LLM-written reply, the one place in the request path where a
model writes free text about a supplier question.

End to end, that reply is produced only when the classifier's LLM decides COORDINATOR. In the
live runs it never did (it failed, or chose INVENTORY 4 of 4 times), and the Gemini free-tier
quota is used up for the day. So this script calls the app's own select_coordinator_reply()
with the routing result it would receive in that case (decided_by=LLM, rule_id=llm.classify).
Everything after routing is the app's real code: COORDINATOR_DIRECT_REPLY_PROMPT, the hybrid
Gemini -> Groq provider, max_tokens=200, the app's own LLM timeout. Nothing is changed.

Run from the repository root:
    venv\\Scripts\\python audit\\bias_2026-10-07\\run_reply_component.py
"""
import datetime
import json
import logging
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from agents.coordinator.intent_classifier import IntentResult  # noqa: E402
from agents.coordinator.router import select_coordinator_reply  # noqa: E402
from config.llm_config import llm_config  # noqa: E402
from config.settings import settings  # noqa: E402
from run_bias_audit import ATTRIBUTE_WORDS, FORMS, REPEATS, TESTS, recommendation  # noqa: E402

PROVIDER_EVENTS = ("LLM_GEMINI_SUCCESS", "LLM_GEMINI_FAILED", "LLM_GROQ_FALLBACK_SUCCESS", "LLM_GROQ_FAILED",
                   "LLM_ALL_PROVIDERS_FAILED")


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.events = []

    def emit(self, record):
        msg = record.getMessage()
        for name in PROVIDER_EVENTS:
            if name in msg:
                self.events.append({"event": name, "detail": msg[msg.find("{"):][:300]})


def main():
    capture = Capture()
    logging.getLogger().addHandler(capture)
    routed = IntentResult("COORDINATOR", 0.9, "LLM chose COORDINATOR (simulated routing result)", "llm",
                          rule_id="llm.classify", decided_by="llm", llm_status="ok", llm_consulted=True)
    runs = []
    for rep in range(1, REPEATS + 1):
        for test_id, test in TESTS.items():
            first, second = test["labels"]
            g1, g2 = test["groups"]
            for orientation, labels, groups in (("initial", {"a": first, "b": second}, {"Northbay": g1, "Eastgate": g2}),
                                                ("swapped", {"a": second, "b": first}, {"Northbay": g2, "Eastgate": g1})):
                prompt = FORMS["plain"].format(**labels)
                capture.events = []
                started = time.perf_counter()
                text, reply_rule, decided_by, llm_status = select_coordinator_reply(prompt, routed)
                run = {
                    "test": test_id, "attribute": test["attribute"], "orientation": orientation, "repeat": rep,
                    "sent_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "prompt": prompt, "groups_by_supplier": groups,
                    "settings": {"gemini_model": llm_config.GEMINI_MODEL, "groq_model": llm_config.GROQ_MODEL,
                                 "groq_temperature": 0.3, "max_tokens": 200, "llm_timeout_s": settings.LLM_TIMEOUT_S},
                    "reply_rule": reply_rule, "decided_by": decided_by, "llm_status": llm_status,
                    "provider_events": capture.events, "duration_s": round(time.perf_counter() - started, 1),
                    "response_text": text,
                    "attribute_words_in_response": sorted({m.lower() for m in ATTRIBUTE_WORDS.findall(text)}),
                    "recommendation": recommendation(text, groups),
                }
                runs.append(run)
                print(f"{test_id} {orientation:7s} #{rep}: {reply_rule} {llm_status} "
                      f"{[e['event'] for e in capture.events]} pick={run['recommendation']['recommended']} "
                      f"attr={run['attribute_words_in_response']} {text[:140]!r}")
    (HERE / "runs_reply_component.json").write_text(json.dumps(runs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saved {len(runs)} runs")


if __name__ == "__main__":
    main()
