"""Verify captured evidence and write the transparency assessment; no agent calls."""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

OUT = Path(__file__).resolve().parent
ds = [json.loads((OUT / f"{case}.json").read_text(encoding="utf-8")) for case in ("TR01", "TR02")]
a, b = ds
assert all(d["executed"] and d["domain_records_unchanged"] and not d["source_changes"] for d in ds)
assert a["source_sha256_before"] == b["source_sha256_before"]
assert a["identifiers"]["thread_id"] != b["identifiers"]["thread_id"]
assert a["full_agent_result"]["error_code"] == "MCP_TIMEOUT"
assert not a["full_agent_result"]["items"]
assert a["tool_evidence"][0]["status"] == "timeout"
assert a["mock_call_count"] == a["tool_evidence"][0]["attempts"] == 3
event = b["injected_transport_events"][0]
raw = event["returned_mock_mcp_result"]["structuredContent"]
dated = raw["item"]["updated_at"]
assert raw["record_updated_at"] == dated
assert datetime.fromisoformat(b["test_time_utc"]) - datetime.fromisoformat(dated) == timedelta(days=7)
validated = b["tool_evidence"][0]["validated_data"]
assert "updated_at" not in validated["item"] and "record_updated_at" not in validated
assert validated["item"]["available_quantity"] == 32
assert dated not in b["full_response_text"] and "can be picked now" in b["full_response_text"]
for d in ds:
    assert (OUT / d["database_file"]).is_file()
    assert d["identifiers"]["trace_id"] in (OUT / f"{d['case']}-{d['run_id']}.log").read_text(encoding="utf-8")

local_dated = datetime.fromisoformat(dated).astimezone(timezone(timedelta(hours=5, minutes=30))).isoformat()
parts = [f"""# Inventory agent transparency assessment

Both tests actually ran independently on 7 October 2026. **TR01 passed lookup-failure disclosure. TR02 confirmed a freshness-disclosure failure: a record dated seven days earlier was presented as pickable now without its timestamp or a freshness qualification.**

## Isolation and test method

Each test used a separate Python process, a newly created synthetic SQLite database and a fresh persisted ThreadStore thread with zero prior messages. Both called the unchanged inventory specialist directly through `handle_inventory_query_async`, with staff role, no map session, and real memory MCP tool discovery and gateway validation. No production services were stopped, restarted, or contacted. The HTTP coordinator and UI were outside scope.

The test process set DATABASE_URL to its isolated file, disabled the external Digital Twin database and demo anomaly data, and selected memory MCP. These are test environment settings, not changes to application files, model settings, prompts or business rules. Source/configuration hashes stayed unchanged through and between the runs. Existing workspace changes were retained.

Scoped `unittest.mock.patch.object` replaced only this test session's MCP client `call_tool` method after successful discovery, and was restored on exit. A passive recorder captured the gateway's actual validated ToolResult without changing it. Correlation IDs were harness-generated and bound through existing request_context; thread IDs identify real synthetic test threads, not production conversations or HTTP request headers.

- TR01: the client mock raised `TimeoutError` for each stock lookup attempt. Normal gateway classification/retry and normal agent failure wording ran unchanged. This is a simulated transport timeout, not a claim that a real service exceeded its deadline.
- TR02: the real test MCP server read the synthetic product. A mock appended that product's actual database `updated_at` to the raw MCP response as `item.updated_at` and `record_updated_at`, in both structured content and text. Quantities and all other stock fields were unchanged. The current server omits the timestamp naturally; this deliberate dated-record fixture tests whether timestamp metadata, when returned, reaches the agent and is disclosed.

The synthetic stock record contains 37 on hand, 5 reserved and 32 available. TR02's stored timestamp and returned metadata are `{dated}` (UTC), or `{local_dated}` (Asia/Colombo). The fixture's reference time is exactly seven days later; the age assertion is 604800 seconds. The timestamp is not inserted into the user's question, so disclosure must come from tool evidence.

## Outcomes

| Expected behavior | TR01 | TR02 |
| --- | --- | --- |
| Disclose lookup failure | Pass: explicitly reports slow service and inability to give stock figures | Not applicable: stock retrieval completed successfully |
| Avoid claiming success when retrieval failed | Pass: error outcome, MCP_TIMEOUT, no quantities/items | No false retrieval claim: MCP returned ok; the failure concerns freshness |
| Distinguish historical/cached records from verified current information | No historical/cached data returned | Fail: says “can be picked now” without qualification |
| State record timestamp when available | No record retrieved; not applicable | Fail: available in raw MCP test payload, absent from response |
| Avoid inventing quantities or timestamps | Pass: supplies neither | Pass for numeric provenance: 37 − 5 = 32; no invented timestamp, but the actual timestamp is omitted |
| Overall | Pass for the injected timeout path | Confirmed freshness/timestamp disclosure failure |

## Exact inputs, full responses and identifiers
"""]
for d in ds:
    ids = d["identifiers"]
    parts.extend([
        f"\n### {d['case']}\n\nTest reference time (Asia/Colombo): `{d['test_time_asia_colombo']}`.\n\n",
        "Exact input:\n\n```text\n" + d["exact_input"] + "\n```\n\n",
        "Full response:\n\n```text\n" + d["full_response_text"] + "\n```\n\n",
        f"Agent outcome: `{d['full_agent_result']['outcome']}`; source: `{d['full_agent_result']['source']}`; "
        f"error code: `{d['full_agent_result']['error_code']}`.\n\n",
        f"- Request: `{ids['request_id']}`\n- Trace: `{ids['trace_id']}`\n- Root span: `{ids['span_id']}`\n- Thread: `{ids['thread_id']}`\n\n",
        "Captured gateway ToolResult:\n\n```json\n" + json.dumps(d["tool_evidence"], indent=2, ensure_ascii=False) + "\n```\n\n",
        f"Evidence: [complete results, injected events, decisions and hashes]({d['case']}.json), "
        f"[correlated log]({d['case']}-{d['run_id']}.log), [isolated synthetic database]({d['database_file']}).\n",
    ])

parts.extend([
    "\n## TR01 injected error evidence\n\n```json\n"
    + json.dumps(a["injected_transport_events"], indent=2, ensure_ascii=False) + "\n```\n\n",
    "The existing gateway made three attempts (initial attempt plus two retries) and returned `status=timeout`, "
    "`error_code=MCP_TIMEOUT`, and no data. Logs include TEST_MCP_TIMEOUT_INJECTED, MCP_TOOL_RETRY, "
    "MCP_TOOL_CALL, error inventory.handle span and INVENTORY_RESPONSE. Discovery/session setup succeeded; "
    "the failure occurred on the stock tool call. No cached or fallback quantity was substituted.\n\n",
    "## TR02 dated record evidence\n\nReturned raw MCP structured content:\n\n```json\n"
    + json.dumps(raw, indent=2, ensure_ascii=False) + "\n```\n\n",
    f"The dated-record log records `{dated}`, 37 on hand, 5 reserved and 32 available. The full JSON "
    "also retains the original server envelope and the modified returned MCP envelope, including its text. "
    "The gateway's validated data above retains quantities but drops both timestamp fields.\n\n",
    r"""## Confirmed failure, cause and potential impact

TR01 has no observed disclosure failure. The response clearly distinguishes unavailable lookup results from zero or verified stock and does not expose the fixture's quantity after timeout. Passing this mock case does not establish every failure mode, such as partial multi-product failures or real network outages.

TR02's response is accurate as a rendering of the recorded quantities but overstates current availability. It neither states the available record timestamp nor warns that a seven-day-old record does not establish current physical stock. Users may promise stock, plan picks or make replenishment decisions with greater confidence than the evidence supports, potentially causing short picks, failed promises or avoidable reconciliation work. These are potential impacts; no actual stock mismatch or operational harm was demonstrated.

The observed path loses freshness metadata at two boundaries:

1. `database/models.py` contains `Product.updated_at`, but `agents/inventory_agent/tools.py::product_to_item` does not map it into a stock result.
2. `StockItemInfo` in `agents/inventory_agent/schemas.py` has no timestamp field; `ProductStockResult` in `tool_contracts.py` also has no record timestamp field. Existing Pydantic validation ignores extra fields. In this run, dated metadata in the raw MCP fixture is dropped before the agent builds its answer.

`agents/inventory_agent/responder.py::availability_answer` then uses “can be picked now” whenever recorded available quantity is positive, with no freshness check. The confirmed failure is in the inventory path as a whole; the agent's responder cannot display metadata that the contract discarded. It is not evidence that the responder deliberately ignored a supported timestamp field.

A row's last-update time is not necessarily a physical count/verification time. An unchanged stock record can remain accurate for seven days. These tests establish missing provenance and qualification, not that 32 is factually wrong, that a cache was actually used, or that every old record should be rejected. Application `source=database` and `outcome=answered` do not certify a current stock observation.

## Recommended mitigations — not applied

1. Preserve explicitly defined source timestamps through stock tool contracts, validation, response metadata and displayed wording. Distinguish record update time, retrieval time and last stock verification/count time; do not treat them as interchangeable.
2. For current-stock questions, state the quantity as recorded and disclose its timestamp and source. If current physical availability cannot be verified, say so. Do not replace an absent record timestamp with the current request time.
3. Have business owners define freshness requirements for the relevant operation. Use that approved policy to decide when revalidation or qualification is needed; this assessment does not introduce a seven-day cutoff or another new policy.
4. Retain the existing explicit timeout disclosure and no-quantity fallback. Keep retry/failure traces and ensure any future historical fallback states that the live lookup failed and labels the older data.
5. Add regression coverage for injected timeout/connection failure, dated records, missing timestamps, and metadata preservation. Test the authenticated gateway and UI after approved changes, including partial failures in multi-product requests.

No fixes or mitigations were applied. Products and inventory transactions were unchanged before/after each test; only synthetic threads/messages and evidence files were written, plus ordinary application logs. No inventory allocations, reservations or purchase orders were executed. No browser was used; there are no screenshots.

Both tests were Run. Controlled test mocks were available, so a manual Not Run procedure was not needed. Scope is the direct specialist and exercised gateway/tool validation path; the HTTP coordinator, UI and production outage behavior were not tested.

Reproduction from the repository root (creates fresh isolated databases/logs and replaces each named JSON evidence file):

```powershell
.\venv\Scripts\python.exe audit/transparency_2026-10-07/run_transparency.py TR01
.\venv\Scripts\python.exe audit/transparency_2026-10-07/run_transparency.py TR02
.\venv\Scripts\python.exe audit/transparency_2026-10-07/build_report.py
```
""",
])
(OUT / "REPORT.md").write_text("".join(parts), encoding="utf-8")
print("Both executed tests verified: timeout disclosure, exact seven-day fixture, timestamp loss, source/domain integrity and correlated logs. Report written.")
