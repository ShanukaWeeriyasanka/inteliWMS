"""
Document Parser & Inbound Supplier NER for Inventory Agent (Member 1).

Extracts:
  - SKU (e.g. SKU-4521, SKU-1088), or a product inferred from its name
  - Quantity and its unit (e.g. 200 units, 50 rolls, 40 cartons)
  - Delivery Date (e.g. 2026-10-05, tomorrow, Friday, next Monday, Oct 12, in 3 days)
  - Supplier Name / Email (e.g. Apex Logistics, Zebra Supplies)
  - PO Reference / Manifest Number

Drafts a restock request for manager approval, but only from facts the document states:
nothing missing is filled in with a default. A missing quantity, date or PO is reported as
"not stated", and with no product or no quantity no restock request is drafted at all.
"""
import re
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from agents.inventory_agent.schemas import (
    DocumentParseResult,
    ParsedEntity,
    DraftRestockOrder,
)
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

NOT_STATED = "not stated in the document"

# Patterns for extraction
SKU_PATTERN = re.compile(r"\b(SKU-\d{3,6})\b", re.IGNORECASE)
# A reference needs a digit: "Order confirmed" is not PO "CONFIRMED"
PO_PATTERN = re.compile(r"\b(?:PO|P\.O\.|Order|Manifest|Invoice)\s*[:#-]?\s*((?=[A-Z0-9-]*\d)[A-Z0-9-]{4,12})\b",
                        re.IGNORECASE)
SUPPLIER_PATTERN = re.compile(r"\b(?:From|Supplier|Vendor|Carrier|Sender)\s*[:\-]\s*([A-Za-z0-9\s&]+?)(?:\n|<|,|\.|$)", re.IGNORECASE)

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_SLASH_DATE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
# Real month names only ("decided 5" is not 5 December)
_MONTH_DATE = re.compile(r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
                         r"sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+(\d{1,2})(?:st|nd|rd|th)?"
                         r"(?:,?\s+(\d{4}))?\b", re.IGNORECASE)
_RELATIVE_DAY = re.compile(r"\b(today|tomorrow)\b", re.IGNORECASE)
_WEEKDAY = re.compile(r"\b(?:(this|next|on|by|coming)\s+)?(" + "|".join(_WEEKDAYS) + r")\b", re.IGNORECASE)
_IN_DAYS = re.compile(r"\bin\s+(\d{1,2})\s+(?:business\s+|working\s+)?days?\b", re.IGNORECASE)

# Quantity: a number followed by a unit, a labelled quantity, or a shipping verb before the number
_UNITS = (r"units?|pcs|pieces?|rolls?|boxes|box|cases?|cartons?|ctns?|pallets?|packs?|crates?|kits?|bundles?|"
          r"drums?|bags?|items?|batteries|scanners?|printers?|labels?")
_NUMBER = r"(\d{1,3}(?:,\d{3})+|\d{1,6})"
_QTY_WITH_UNIT = re.compile(rf"\b{_NUMBER}\s*(?:x\s*)?({_UNITS})\b", re.IGNORECASE)
_QTY_LABELLED = re.compile(rf"\b(?:qty|quantity|count|total)\s*(?:of\s*)?[:=#-]?\s*{_NUMBER}\b", re.IGNORECASE)
_QTY_AFTER_VERB = re.compile(rf"\b(?:shipped|shipping|ships|delivering|delivered|sending|sent|dispatching|dispatched)"
                             rf"\s+{_NUMBER}\b", re.IGNORECASE)

KNOWN_SUPPLIERS = [
    "Apex Automotive Supplies",
    "Zebra Technologies Direct",
    "PackPro Industrial Logistics",
    "Global Forklift Spares Ltd",
    "LithiumTech Energy Systems",
    "Horizon Freight & Materials"
]

KNOWN_SKU_NAMES = {
    "SKU-4521": "Wireless Barcode Scanner",
    "SKU-7788": "Thermal Label Printer",
    "SKU-9012": "Heavy Duty Pallet Wrap",
    "SKU-1088": "Thermal Industrial Label Rolls",
    "SKU-2045": "Heavy Duty Forklift Battery Lithium"
}

# Product name keywords → SKU (used only when the document names no SKU; the agent checks it exists)
_NAME_HINTS: List[Tuple[Tuple[str, ...], str]] = [
    (("barcode scanner", "scanner"), "SKU-4521"),
    (("thermal printer", "label printer", "printer"), "SKU-7788"),
    (("pallet wrap", "shrink wrap", "stretch wrap"), "SKU-9012"),
    (("label rolls", "label roll", "barcode labels"), "SKU-1088"),
    (("forklift battery", "lithium battery"), "SKU-2045"),
]


def _to_int(text: str) -> int:
    return int(text.replace(",", ""))


def _next_weekday(today: date, weekday: int, qualifier: str) -> date:
    ahead = (weekday - today.weekday()) % 7
    if ahead == 0 and qualifier == "next":
        ahead = 7  # "next Friday" said on a Friday is a week away
    return today + timedelta(days=ahead)


def extract_delivery_date(text: str, today: Optional[date] = None) -> Tuple[Optional[str], Optional[str], Optional[Tuple[int, int]]]:
    """(display value, raw text, span) of the delivery date the text states; (None, None, None) when none."""
    today = today or date.today()
    m = _ISO_DATE.search(text)
    if m:
        return m.group(0), m.group(0), m.span()
    m = _MONTH_DATE.search(text)
    if m:
        month = _MONTHS.index(m.group(1).lower()[:3]) + 1
        year = int(m.group(3)) if m.group(3) else today.year
        try:
            return date(year, month, int(m.group(2))).isoformat(), m.group(0), m.span()
        except ValueError:
            return m.group(0), m.group(0), m.span()
    m = _SLASH_DATE.search(text)
    if m:
        return m.group(0), m.group(0), m.span()  # day/month order is ambiguous: shown as written
    m = _RELATIVE_DAY.search(text)
    if m:
        offset = 0 if m.group(1).lower() == "today" else 1
        return f"{m.group(1).lower()} ({(today + timedelta(days=offset)).isoformat()})", m.group(0), m.span()
    m = _IN_DAYS.search(text)
    if m:
        return f"in {m.group(1)} days ({(today + timedelta(days=int(m.group(1)))).isoformat()})", m.group(0), m.span()
    m = _WEEKDAY.search(text)
    if m:
        qualifier = (m.group(1) or "").lower()
        day_name = m.group(2).lower()
        resolved = _next_weekday(today, _WEEKDAYS.index(day_name), qualifier)
        return f"{day_name.capitalize()} ({resolved.isoformat()})", m.group(0), m.span()
    return None, None, None


def extract_quantity(text: str) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """(quantity, unit, raw text). Codes and dates must already be masked out of `text`."""
    m = _QTY_WITH_UNIT.search(text)
    if m:
        unit = m.group(2).lower()
        return _to_int(m.group(1)), unit, m.group(0)
    for pattern in (_QTY_LABELLED, _QTY_AFTER_VERB):
        m = pattern.search(text)
        if m:
            return _to_int(m.group(1)), None, m.group(0)
    return None, None, None


def _mask(text: str, spans: List[Tuple[int, int]]) -> str:
    """Blank out codes and dates so their digits are never read as a quantity."""
    chars = list(text)
    for start, end in spans:
        for i in range(start, end):
            chars[i] = " "
    return "".join(chars)


def _infer_sku_from_name(text: str) -> Optional[str]:
    lower = text.lower()
    for words, sku in _NAME_HINTS:
        if any(w in lower for w in words):
            return sku
    return None


def new_draft_id() -> str:
    """Unique per draft (two documents in the same second no longer share an id)."""
    return f"RST-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"


def summarise(doc_type: str, supplier: str, item_name: Optional[str], sku: Optional[str], qty: Optional[int],
              unit: Optional[str], delivery: Optional[str], po_ref: Optional[str],
              draft: Optional[DraftRestockOrder], problems: List[str]) -> str:
    item = (f"**{item_name}** (`{sku}`)" if item_name else f"`{sku}`") if sku else "not identified"
    qty_text = f"**{qty}** {unit or 'units'}" if qty is not None else NOT_STATED
    lines = [
        f"📄 Parsed {doc_type.replace('_', ' ').title()} from **{supplier}**.",
        f"• Extracted Item: {item}",
        f"• Quantity: {qty_text}",
        f"• Expected Arrival: {delivery or NOT_STATED}",
        f"• PO Reference: `{po_ref}`" if po_ref else f"• PO Reference: {NOT_STATED}",
    ]
    if draft:
        lines.append(f"✅ Restock Request **{draft.draft_id}** drafted for Floor Manager approval.")
    else:
        lines.append("⚠️ No restock request was drafted: " + "; ".join(problems) + ".")
    return "\n".join(lines)


class DocumentParser:
    """Specialist sub-module for parsing unstructured supplier correspondence."""

    def parse_document(self, text: str, today: Optional[date] = None) -> DocumentParseResult:
        logger.log_event("DOCUMENT_PARSER_INVOKED", {"text_preview": text[:80]})

        entities: List[ParsedEntity] = []
        raw = text.strip()
        masked_spans: List[Tuple[int, int]] = []

        # 1. SKU (or a product inferred from its name — the agent checks it exists)
        sku_match = SKU_PATTERN.search(raw)
        extracted_sku = sku_match.group(1).upper() if sku_match else None
        if sku_match:
            entities.append(ParsedEntity(entity_type="SKU", value=extracted_sku, raw_text=sku_match.group(0)))
        else:
            extracted_sku = _infer_sku_from_name(raw)
            if extracted_sku:
                entities.append(ParsedEntity(entity_type="SKU", value=extracted_sku, raw_text="Inferred from product name"))
        masked_spans += [m.span() for m in SKU_PATTERN.finditer(raw)]

        # 2. PO reference (only a stated one — never invented)
        po_match = PO_PATTERN.search(raw)
        po_ref = po_match.group(1).upper() if po_match else None
        if po_match:
            entities.append(ParsedEntity(entity_type="PO_NUMBER", value=po_ref, raw_text=po_match.group(0)))
            masked_spans.append(po_match.span())

        # 3. Delivery date (relative dates are resolved against today and shown with both forms)
        delivery, date_raw, date_span = extract_delivery_date(raw, today)
        if delivery:
            entities.append(ParsedEntity(entity_type="DELIVERY_DATE", value=delivery, raw_text=date_raw))
            masked_spans.append(date_span)

        # 4. Quantity and its unit, read with codes and dates masked out
        qty, unit, qty_raw = extract_quantity(_mask(raw, masked_spans))
        if qty is not None:
            entities.append(ParsedEntity(entity_type="QUANTITY", value=qty, raw_text=qty_raw))

        # 5. Supplier
        supplier_name: Optional[str] = None
        sup_match = SUPPLIER_PATTERN.search(raw)
        if sup_match:
            supplier_name = sup_match.group(1).strip()
        else:
            for s in KNOWN_SUPPLIERS:
                if s.lower() in raw.lower() or re.search(rf"\b{re.escape(s.split()[0])}\b", raw, re.IGNORECASE):
                    supplier_name = s
                    break
        if not supplier_name:
            supplier_name = "an unnamed supplier"
        entities.append(ParsedEntity(entity_type="SUPPLIER", value=supplier_name, raw_text=supplier_name))

        # 6. Draft restock request — only when the product and the quantity are both stated
        problems = []
        if not extracted_sku:
            problems.append("the document doesn't say which product (add a SKU or the product name)")
        if qty is None:
            problems.append("the quantity isn't stated")
        elif qty <= 0:
            problems.append("the quantity must be more than zero")
        item_name = KNOWN_SKU_NAMES.get(extracted_sku, "Warehouse Stock Item") if extracted_sku else None
        draft_order = None
        if not problems:
            draft_order = DraftRestockOrder(
                draft_id=new_draft_id(),
                supplier_name=supplier_name,
                sku=extracted_sku,
                item_name=item_name,
                quantity=qty,
                promised_delivery_date=delivery or NOT_STATED,
                status="DRAFT_PENDING_APPROVAL",
                notes=(f"Auto-generated from inbound supplier document ({po_ref or 'no PO reference'}) "
                       f"by Document Parser NER."),
            )

        doc_type = "supplier_email" if any(w in raw.lower() for w in ["email", "subject:", "hi team", "regards", "dear"]) else "supplier_pdf"
        stated = sum(x is not None for x in (extracted_sku, qty, delivery, po_ref))
        return DocumentParseResult(
            document_type=doc_type,
            supplier_name=supplier_name,
            extracted_sku=extracted_sku,
            extracted_quantity=qty,
            quantity_unit=unit,
            extracted_delivery_date=delivery,
            po_reference=po_ref,
            confidence=round(0.5 + 0.12 * stated, 2),
            entities=entities,
            draft_order=draft_order,
            problems=problems,
            raw_summary=summarise(doc_type, supplier_name, item_name, extracted_sku, qty, unit, delivery, po_ref,
                                  draft_order, problems),
        )


document_parser = DocumentParser()
