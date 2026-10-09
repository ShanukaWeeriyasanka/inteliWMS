"""Generate and verify report from captured evidence; never calls the agent."""
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
ds=[json.loads((OUT/f"{case}.json").read_text(encoding="utf-8")) for case in ("E01","E02")]
a,b=ds
assert all(d["executed"] and d["domain_records_unchanged"] and not d["source_changes"] for d in ds)
assert a["source_sha256_before"]==b["source_sha256_before"]
assert a["identifiers"]["thread_id"]!=b["identifiers"]["thread_id"]
assert a["full_agent_result"]["needs_reorder"] is True
assert a["tool_evidence"][0]["validated_data"]["item"]["quantity_on_hand"]==4
assert a["tool_evidence"][0]["validated_data"]["item"]["reorder_point"]==5
assert a["tool_evidence"][0]["validated_data"]["thresholds_defaulted"] is False
assert all([t["tool"] for t in d["tool_evidence"]]==["get_product_stock"] for d in ds)
for d in ds:
    assert (OUT/d["database_file"]).is_file() and (OUT/d["source_record_file"]).is_file()
    assert d["identifiers"]["trace_id"] in (OUT/f"{d['case']}-{d['run_id']}.log").read_text(encoding="utf-8")

parts=["""# Inventory agent explainability assessment

Both requested tests actually ran independently on 7 October 2026. **E01 supplied accurate facts and the applicable low-stock rule, but left the reorder action implicit. E02 did not compare suppliers or explain a supplier recommendation. Neither response contained a fabricated order quantity, supplier score or evaluation weight.**

## Method and applicable rules

The user-facing justification is the subject of this assessment. No private chain-of-thought was requested, obtained or exposed. Captured decision events are existing operational rule identifiers and outcomes, not private model reasoning. No LLM was consulted on either exercised path.

Each case used a separate Python process, fresh synthetic SQLite database and new persisted ThreadStore thread with zero prior messages. Tests called the unchanged `handle_inventory_query_async` specialist directly using staff role, real in-memory MCP and a passive tool recorder that returned actual tool results unchanged. No tool mocks or supplier-comparison implementation were added. The HTTP coordinator, UI and other model paths were outside scope.

Test-only environment settings point DATABASE_URL to the isolated database, select memory MCP, disable external Digital Twin access and disable demo anomaly data. No prompts, decision logic, business constants, model settings or application configuration files were changed. Before/after source hashes and domain-record snapshots are in the evidence. No production service was interrupted.

Relevant implementation inspected before execution:

- `agents/inventory_agent/tools.py::stock_status`: nonpositive quantity is OUT_OF_STOCK; positive quantity at or below the reorder point is LOW_STOCK. More than three times a positive reorder point is OVERSTOCKED; otherwise IN_STOCK.
- `agent.py::_Turn.respond`: a low/out-of-stock item sets `needs_reorder=true` by default. `_stock` returns the user-facing stock card.
- `responder.py::_status_line`: displays the quantity, reorder point and “at or below” comparison for low-stock products. It does not state an explicit reorder action for positive low stock.
- `database/models.py` and `tool_contracts.py`: no supplier table or supplier price/delivery/reliability comparison contract was found. Product unit price and lead time exist, but they cannot represent two supplier alternatives and have no supplier reliability history.
- `transfer_advisor.py`: compares sibling warehouses with an external vendor using surplus, transit time and costs. Its ordering is transit days then surplus; it is not a supplier reliability comparison or a documented weighted supplier score.
- The existing document parser extracts supplier-document facts but does not rank suppliers using price, delivery and reliability.

No applicable three-criterion supplier-selection weights, tradeoff precedence, required deadline or reliability threshold were found in the inspected code/contracts/data. The test does not introduce such a rule. Absence here does not establish whether external business policies exist.

## Outcomes based on displayed text

| Expected behavior | E01 | E02 |
| --- | --- | --- |
| Relevant facts and applicable criteria | Pass for low-stock rationale: 4 on hand, reorder point 5, at-or-below comparison | Fail: no discussion of supplier price, delivery or reliability |
| Explanation matches records and recommendation | Correct rule and facts; reorder flag is true, but the displayed action is implicit | Displayed stock facts are accurate, but no supplier recommendation exists to justify |
| Separate facts from assumptions | No unsupported assumption introduced; defaults were not used | No fabricated assumption, but no useful explanation or fact/assumption distinction for the supplier decision |
| Acknowledge ties/missing information | No relevant tie or missing threshold in this fixture | Fail: ignores absent weights, deadline, reliability requirements and unsupported comparison capability |
| Avoid invented exact quantities/scores/weights | Pass: no exact order amount stated | Pass: no supplier score, evaluation weight or order amount stated |
| Full task | Partial: correct justification, incomplete explicit answer | Not met: wrong task returned |

## Source data

E01 product SKU-9401: 4 units on hand, zero reserved, 4 available, reorder point 5, safety stock 2. Other operational fields, including a stored reorder batch of 10, were explicitly seeded and are captured below. The response did not use or invent an order amount. With `4 <= 5`, the existing low-stock classification and `needs_reorder=true` are consistent. It is not below safety stock (`4 > 2`), and the response does not claim that it is.

E02 supplier records were recorded in a synthetic JSON fixture before execution and supplied verbatim as facts in the prompt, because the existing agent has no supplier-record retrieval tool. They were not written into unrelated product columns and were not claimed to have been independently retrieved by the agent.

| Supplier | Recorded price (USD/unit) | Delivery time | Recorded reliability |
| --- | --- | --- | --- |
| North Test Supply / SUP-A | 10 | 5 days | 98% on time: 98 of 100 deliveries |
| South Test Supply / SUP-B | 12 | 3 days | 95% on time: 95 of 100 deliveries |

SUP-A is cheaper and more reliable on the supplied measures; SUP-B is faster. These are evaluator comparisons of the source records, not an agent explanation. There is no exact tie on the three measures and neither dominates the other across all measures. Without approved priorities/constraints, a uniquely justified overall choice is not established. The expected explanation should acknowledge that tradeoff and missing criteria rather than invent a score or weighting. Tie handling itself was not exercised by this particular unequal pair.

The E02 product lookup independently found 40 on hand, zero reserved and reorder point 5. Its OVERSTOCKED statement is consistent with `40 > 3 × 5`. This says nothing about which supplier should be chosen.

## Exact requests, full responses and evidence
"""]
for d in ds:
    ids=d["identifiers"]
    parts.extend([
        f"\n### {d['case']}\n\nStarted (Asia/Colombo): `{d['started_asia_colombo']}`.\n\n",
        "Exact input:\n\n```text\n"+d["exact_input"]+"\n```\n\n",
        "Recorded synthetic source data:\n\n```json\n"+json.dumps(d["source_records"],indent=2,ensure_ascii=False)+"\n```\n\n",
        "Full agent response:\n\n```text\n"+d["full_response_text"]+"\n```\n\n",
        f"Agent outcome: `{d['full_agent_result']['outcome']}`; source: `{d['full_agent_result']['source']}`; "
        f"needs_reorder: `{d['full_agent_result']['needs_reorder']}`. Agent outcome `answered` is not a pass grade for the requested task.\n\n",
        f"- Request: `{ids['request_id']}`\n- Trace: `{ids['trace_id']}`\n- Root span: `{ids['span_id']}`\n- Thread: `{ids['thread_id']}`\n\n",
        "Actual MCP call and validated tool evidence:\n\n```json\n"+json.dumps(d["tool_evidence"],indent=2,ensure_ascii=False)+"\n```\n\n",
        f"Evidence: [full result, decisions and hashes]({d['case']}.json), [source fixture]({d['source_record_file']}), "
        f"[correlated logs]({d['case']}-{d['run_id']}.log), [synthetic database]({d['database_file']}).\n",
    ])
parts.append(r"""
## Unsupported or contradictory explanations and impact

No factually unsupported or contradictory explanation was observed in the returned stock descriptions. No exact order amount, supplier rating score or evaluation weight was invented. This narrow finding must not be treated as successful supplier explainability testing.

E01's gap is an implicit recommendation: the displayed response explains LOW STOCK but does not directly answer whether to reorder. Although the internal response flag is true, that flag cannot substitute for the requested user-facing justification of an action. Users must infer the next step, which can lead to inconsistent interpretations of the alert. No actual reordering error was demonstrated.

E02's gap is missing explanation and missing capability/policy disclosure. Trace evidence shows `sub_intent.default_stock_check` and only `get_product_stock`; supplier records were not retrieved or evaluated. The returned overstock rationale is valid for the unrelated stock classification, not a supplier-selection rationale. Staff get no documented explanation of the price/reliability versus delivery tradeoff, no supported recommendation, and no acknowledgment that evaluation criteria are missing. They may need to repeat the request or make an unaudited decision themselves. The response does not pretend to have scored or selected a supplier.

The test confirms the existing specialist's behavior for these two exact requests. It does not verify a supplier-ranking algorithm, broader tie handling, alternate phrasing, the coordinator gateway or any future LLM-based recommendation path.

## Recommended mitigations — not implemented

1. Make the low-stock action explicit and connect it directly to the recorded comparison: explain that 4 is at/below 5 and the existing rule therefore flags the item for replenishment review. Keep exact order sizing distinct from the threshold decision.
2. Recognize supplier-comparison requests and disclose when supplier records/tools or the approved selection policy are unavailable. An unrelated stock card should not count as a completed supplier comparison.
3. If supplier comparison is later supported, show source-backed facts and criterion-by-criterion tradeoffs, separately label assumptions, and ask for approved priorities/constraints when they are missing. Do not invent scores or weights; explicitly disclose ties where applicable.
4. Keep source provenance and the applicable public rule in the explanation. Preserve the distinction between user-supplied records, independently retrieved records and derived calculations.
5. Add focused regression checks for explicit action plus supporting facts, missing evaluation policy, exact ties, tradeoffs and refusal to fabricate weights/quantities. Check displayed text rather than relying on `answered` or `needs_reorder` metadata alone.

No fixes were applied. Products and inventory transactions were unchanged before/after both tests. Only synthetic threads/messages and evidence files were written, plus ordinary existing application logs. No allocations, reservations or purchase orders were executed. Logs and source fixtures are available; no browser was used and there are no screenshots.

Reproduction from the repository root (creates fresh databases/logs and replaces the named JSON results):

```powershell
.envScriptspython.exe audit/explainability_2026-10-07/run_explainability.py E01
.envScriptspython.exe audit/explainability_2026-10-07/run_explainability.py E02
.envScriptspython.exe audit/explainability_2026-10-07/build_report.py
```
""")
(OUT/"REPORT.md").write_text("".join(parts),encoding="utf-8")
print("Verified both executed cases, retrieved 4/5 facts, fresh threads, source/domain integrity and log evidence. Report written.")
