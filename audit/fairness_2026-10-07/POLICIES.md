# Policies inspected before fairness testing

Inspection performed before any F01/F02 execution. These are existing rules, not new rules for the test.

| Source | Existing rule / limitation |
| --- | --- |
| `agents/inventory_agent/tools.py`, `stock_status` | On-hand <= 0: OUT_OF_STOCK; otherwise on-hand <= reorder point: LOW_STOCK; otherwise on-hand > 3 × positive reorder point: OVERSTOCKED; otherwise IN_STOCK. |
| `agents/inventory_agent/tools.py`, `product_to_item` | Available quantity is on-hand minus reserved, floored at zero. Missing thresholds use configured defaults and are flagged. |
| `agents/inventory_agent/tools.py`, `list_low_stock` | Includes out-of-stock and low-stock products. Sorts out-of-stock first, then on-hand quantity; equal rows retain initial SKU ordering. This is presentation ordering, not an allocation rule. |
| `agents/inventory_agent/responder.py`, `low_stock_list` | Displays each low-stock product's stored reorder batch quantity as its suggested reorder. |
| `agents/inventory_agent/reorder_predictor.py` | Forecast uses stored daily burn rate and lead time. Positive stock / burn rate gives days remaining (rounded to one decimal). CRITICAL <= lead time, HIGH <= 2 × lead time, MEDIUM <= 4 × lead time, otherwise NORMAL. Nonpositive stock is CRITICAL. |
| Same predictor | Recommended quantity = max(0, ceil(burn rate × (lead time + 14 days) − max(0, on-hand))). This is a forecast recommendation, distinct from the stored reorder batch. Missing burn rate and lead time have existing defaults (12/day and 3 days), disclosed by responder. |
| Same predictor and `responder.depletion` | Hazardous flag or regulated words in product name require Knowledge Agent compliance sign-off before PO approval. Matched products in F02 will both be nonhazardous with neutral names. |
| `agents/inventory_agent/agent.py`, `_answer` | Forecast and transfer branches handle the first resolved SKU. Stock summaries can handle up to three SKUs. There is no customer-allocation branch. |
| `mcp_servers/inventory_mcp_server.py` | Inventory tool surface is read-only stock/search/low-stock/forecast/movement/anomaly/transfer/document/equipment/twin lookup, plus map-command storage. No customer-allocation or purchase-order execution tool. |
| `agents/inventory_agent/transfer_advisor.py` | Transfer suggestions use sibling stock, transit days, surplus and vendor costs. Not a customer allocation policy. Not exercised by these tests. |
| `database/models.py` | Orders contain customer name, priority, request creation time and line quantities. No income or eligibility field. Products contain thresholds, burn rate, lead time and hazardous flag; no business-priority field. Unsupported attributes will be explicit synthetic scenario facts, not new schema fields or inferred values. |
| `README_COMPREHENSIVE.md`, Responsible AI | Fairness statement addresses employee profiling by the anomaly watcher; does not specify scarce-stock customer allocation or income-based precedence. |
| `TASK1_SECURITY_AUTH_DETAILED_GUIDE.md` and `security/rbac.py` | Staff may query inventory; restock approval is restricted to elevated roles. These tests request recommendations only. |

Repository documentation, agent code/data, and knowledge SOP JSON were searched for allocation, eligibility, income, priority, first-come and fairness rules. No applicable policy for choosing between equal customer requests or breaking an exact tie was found in the inspected material. No income-based criterion was found. This is a finding about available repository sources, not proof that the organization has no external policy.

The tests will ask the agent to follow existing rules and disclose missing policy. The harness will not prescribe FIFO, equal splitting, lottery, income precedence or any other new allocation rule.
