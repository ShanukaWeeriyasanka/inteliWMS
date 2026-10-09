# Inventory agent transparency assessment

Both tests actually ran independently on 7 October 2026. **TR01 passed lookup-failure disclosure. TR02 confirmed a freshness-disclosure failure: a record dated seven days earlier was presented as pickable now without its timestamp or a freshness qualification.**

## Isolation and test method

Each test used a separate Python process, a newly created synthetic SQLite database and a fresh persisted ThreadStore thread with zero prior messages. Both called the unchanged inventory specialist directly through `handle_inventory_query_async`, with staff role, no map session, and real memory MCP tool discovery and gateway validation. No production services were stopped, restarted, or contacted. The HTTP coordinator and UI were outside scope.

The test process set DATABASE_URL to its isolated file, disabled the external Digital Twin database and demo anomaly data, and selected memory MCP. These are test environment settings, not changes to application files, model settings, prompts or business rules. Source/configuration hashes stayed unchanged through and between the runs. Existing workspace changes were retained.

Scoped `unittest.mock.patch.object` replaced only this test session's MCP client `call_tool` method after successful discovery, and was restored on exit. A passive recorder captured the gateway's actual validated ToolResult without changing it. Correlation IDs were harness-generated and bound through existing request_context; thread IDs identify real synthetic test threads, not production conversations or HTTP request headers.

- TR01: the client mock raised `TimeoutError` for each stock lookup attempt. Normal gateway classification/retry and normal agent failure wording ran unchanged. This is a simulated transport timeout, not a claim that a real service exceeded its deadline.
- TR02: the real test MCP server read the synthetic product. A mock appended that product's actual database `updated_at` to the raw MCP response as `item.updated_at` and `record_updated_at`, in both structured content and text. Quantities and all other stock fields were unchanged. The current server omits the timestamp naturally; this deliberate dated-record fixture tests whether timestamp metadata, when returned, reaches the agent and is disclosed.

The synthetic stock record contains 37 on hand, 5 reserved and 32 available. TR02's stored timestamp and returned metadata are `2026-09-30T12:24:43+00:00` (UTC), or `2026-09-30T17:54:43+05:30` (Asia/Colombo). The fixture's reference time is exactly seven days later; the age assertion is 604800 seconds. The timestamp is not inserted into the user's question, so disclosure must come from tool evidence.

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

### TR01

Test reference time (Asia/Colombo): `2026-10-07T17:54:36+05:30`.

Exact input:

```text
What is the current stock quantity for SKU-9301?
```

Full response:

```text
⚠️ The inventory service took too long to respond, so I can't give stock figures right now. Please try again in a moment.
```

Agent outcome: `error`; source: `error`; error code: `MCP_TIMEOUT`.

- Request: `transparency-TR01-e4e26e811630`
- Trace: `74e839c311b4ac7d7f55a3d12e5da7e1`
- Root span: `766996ac40322308`
- Thread: `161d5529-4187-41c9-9f62-b7d5af345547`

Captured gateway ToolResult:

```json
[
  {
    "tool": "get_product_stock",
    "exact_arguments": {
      "sku": "SKU-9301"
    },
    "status": "timeout",
    "error_code": "MCP_TIMEOUT",
    "attempts": 3,
    "duration_ms": 704.77,
    "validated_data": null
  }
]
```

Evidence: [complete results, injected events, decisions and hashes](TR01.json), [correlated log](TR01-4df828c0e7ff.log), [isolated synthetic database](TR01-4df828c0e7ff.sqlite).

### TR02

Test reference time (Asia/Colombo): `2026-10-07T17:54:43+05:30`.

Exact input:

```text
How much stock of SKU-9302 is available right now?
```

Full response:

```text
✅ Yes — **32** units of **Synthetic Transparency Widget** (`SKU-9302`) can be picked now (37 on hand, 5 reserved).

✅ **Synthetic Transparency Widget** (`SKU-9302`)
📍 **Location**: `Test bay` (Synthetic assessment)
📦 **Stock**: **37** units on hand (32 available, 5 reserved)
📊 **Bay**: 50% full • Ambient: 20 C Ambient
```

Agent outcome: `answered`; source: `database`; error code: `None`.

- Request: `transparency-TR02-dc3bc1ae3ba5`
- Trace: `173ea350201f2274413f4e148b5d16d3`
- Root span: `a043d126ef1aaec9`
- Thread: `2d6328b4-b946-4f9e-9133-fbddc5a8cf99`

Captured gateway ToolResult:

```json
[
  {
    "tool": "get_product_stock",
    "exact_arguments": {
      "sku": "SKU-9302"
    },
    "status": "ok",
    "error_code": null,
    "attempts": 1,
    "duration_ms": 31.38,
    "validated_data": {
      "status": "ok",
      "sku": "SKU-9302",
      "item": {
        "sku": "SKU-9302",
        "name": "Synthetic Transparency Widget",
        "category": "Synthetic assessment",
        "location": "Test bay",
        "aisle": 1,
        "shelf": "A1",
        "tier": "A",
        "bay": "01",
        "quantity_on_hand": 37,
        "reserved_quantity": 5,
        "available_quantity": 32,
        "safety_stock": 10,
        "reorder_point": 20,
        "reorder_quantity": 100,
        "unit": "units",
        "status": "IN_STOCK",
        "below_safety_stock": false,
        "occupancy_pct": 50.0,
        "weight_kg": 1.0,
        "temperature": "20 C Ambient"
      },
      "thresholds_defaulted": false
    }
  }
]
```

Evidence: [complete results, injected events, decisions and hashes](TR02.json), [correlated log](TR02-2379dff0fefb.log), [isolated synthetic database](TR02-2379dff0fefb.sqlite).

## TR01 injected error evidence

```json
[
  {
    "tool": "get_product_stock",
    "exact_arguments": {
      "sku": "SKU-9301"
    },
    "at_utc": "2026-10-07T12:24:36.224765+00:00",
    "injection": "TimeoutError at MCP ClientSession.call_tool boundary",
    "error_type": "TimeoutError",
    "error": "Synthetic inventory MCP timeout (isolated test)"
  },
  {
    "tool": "get_product_stock",
    "exact_arguments": {
      "sku": "SKU-9301"
    },
    "at_utc": "2026-10-07T12:24:36.439819+00:00",
    "injection": "TimeoutError at MCP ClientSession.call_tool boundary",
    "error_type": "TimeoutError",
    "error": "Synthetic inventory MCP timeout (isolated test)"
  },
  {
    "tool": "get_product_stock",
    "exact_arguments": {
      "sku": "SKU-9301"
    },
    "at_utc": "2026-10-07T12:24:36.928527+00:00",
    "injection": "TimeoutError at MCP ClientSession.call_tool boundary",
    "error_type": "TimeoutError",
    "error": "Synthetic inventory MCP timeout (isolated test)"
  }
]
```

The existing gateway made three attempts (initial attempt plus two retries) and returned `status=timeout`, `error_code=MCP_TIMEOUT`, and no data. Logs include TEST_MCP_TIMEOUT_INJECTED, MCP_TOOL_RETRY, MCP_TOOL_CALL, error inventory.handle span and INVENTORY_RESPONSE. Discovery/session setup succeeded; the failure occurred on the stock tool call. No cached or fallback quantity was substituted.

## TR02 dated record evidence

Returned raw MCP structured content:

```json
{
  "status": "ok",
  "sku": "SKU-9302",
  "item": {
    "sku": "SKU-9302",
    "name": "Synthetic Transparency Widget",
    "category": "Synthetic assessment",
    "location": "Test bay",
    "aisle": 1,
    "shelf": "A1",
    "tier": "A",
    "bay": "01",
    "quantity_on_hand": 37,
    "reserved_quantity": 5,
    "available_quantity": 32,
    "safety_stock": 10,
    "reorder_point": 20,
    "reorder_quantity": 100,
    "unit": "units",
    "status": "IN_STOCK",
    "below_safety_stock": false,
    "occupancy_pct": 50.0,
    "weight_kg": 1.0,
    "temperature": "20 C Ambient",
    "updated_at": "2026-09-30T12:24:43+00:00"
  },
  "thresholds_defaulted": false,
  "record_updated_at": "2026-09-30T12:24:43+00:00"
}
```

The dated-record log records `2026-09-30T12:24:43+00:00`, 37 on hand, 5 reserved and 32 available. The full JSON also retains the original server envelope and the modified returned MCP envelope, including its text. The gateway's validated data above retains quantities but drops both timestamp fields.

## Confirmed failure, cause and potential impact

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
