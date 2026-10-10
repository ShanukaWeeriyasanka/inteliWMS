from datetime import date, datetime
from typing import Optional, List
import re
from sqlalchemy.orm import Session
from agents.fulfillment.schemas import FulfillmentRequest, FulfillmentResponse, FulfillmentIntent, SOPSourceCitation
from agents.fulfillment.extractor import extract_order_id
from agents.fulfillment.order_service import get_order_by_id
from agents.fulfillment.intent_classifier import FulfillmentIntentClassifier, fulfillment_intent_classifier
from agents.fulfillment.knowledge_store import FulfillmentKnowledgeStore, fulfillment_knowledge_store
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

class FulfillmentAgent:
    def __init__(
        self,
        classifier: FulfillmentIntentClassifier = None,
        dispatcher=None,
        knowledge_store: Optional[FulfillmentKnowledgeStore] = None
    ):
        self.classifier = classifier or fulfillment_intent_classifier
        self.dispatcher = dispatcher
        self.knowledge_store = knowledge_store or fulfillment_knowledge_store
        self._ensure_knowledge_seeded()

    def _ensure_knowledge_seeded(self):
        """Ensures knowledge store is populated with default demonstration SOPs if empty."""
        try:
            if self.knowledge_store and self.knowledge_store.count() == 0:
                self.knowledge_store.ingest_from_file()
        except Exception as e:
            logger.log_event("FULFILLMENT_SEED_ERROR", {"error": str(e)})

    async def _call_inventory(self, sku: str, user_id: str, role: str, db: Session, user_plan: Optional[str] = None) -> dict:
        if not self.dispatcher:
            from agents.coordinator.agent_dispatcher import dispatch_to_agent
            self.dispatcher = dispatch_to_agent
            
        context_payload = {
            "query": f"check stock for {sku}",
            "user_id": user_id,
            "user_role": role,
            "user_plan": user_plan,
            "caller_agent": "fulfillment_agent",
            "extracted_sku": sku
        }
        return await self.dispatcher("inventory_agent", context_payload, db)

    def _format_citations(self, hits: List[dict]) -> List[SOPSourceCitation]:
        citations = []
        for h in hits:
            citations.append(SOPSourceCitation(
                sop_id=h.get("sop_id", "UNKNOWN"),
                title=h.get("title", "Fulfillment SOP"),
                section_id=h.get("section_id", "SEC-0"),
                heading=h.get("heading", "Procedure"),
                version=h.get("version", "1.0-DEMO"),
                source_file="fulfillment_sops.json",
                status=h.get("status", "demonstration"),
                disclaimer=h.get("disclaimer"),
                similarity_score=h.get("similarity_score"),
                raw_distance=h.get("raw_distance")
            ))
        return citations

    @staticmethod
    def _clean_sop_content(heading: Optional[str], raw_content: Optional[str]) -> str:
        """Strips duplicate leading section heading from chunk text to prevent repetition."""
        if not raw_content:
            return ""
        text = raw_content.strip()
        if heading:
            h = heading.strip()
            pattern = re.compile(rf"^{re.escape(h)}\s*[:\-–—]\s*", re.IGNORECASE)
            text = pattern.sub("", text).strip()
        return text

    def _handle_procedural_query(self, query: str) -> FulfillmentResponse:
        """Handles fulfillment procedural inquiries via vector search and structured grounded formatting."""
        try:
            hits = self.knowledge_store.query(query, top_k=2) if self.knowledge_store else []
        except Exception as e:
            logger.log_event("FULFILLMENT_KNOWLEDGE_QUERY_ERROR", {"error": str(e), "query": query})
            hits = []

        if not hits:
            return FulfillmentResponse(
                success=True,
                order_id=None,
                intent=FulfillmentIntent.FULFILLMENT_PROCEDURE,
                message="No matching documented fulfillment procedure was found for this query. Please consult your warehouse floor supervisor.",
                procedural_guidance=None,
                citations=[],
                information_reliability="no_procedure_found"
            )

        citations = self._format_citations(hits)
        top_hit = hits[0]
        sop_id = top_hit.get("sop_id", "")
        title = top_hit.get("title", "")
        heading = top_hit.get("heading", "")
        content = self._clean_sop_content(heading, top_hit.get("content", ""))

        guidance_text = f"According to {sop_id} ({title}) - {heading}:\n{content}"
        disclaimer_note = "\n\n⚠️ Note: This is an illustrative demonstration SOP requiring warehouse manager approval before operational use."
        full_message = f"{guidance_text}{disclaimer_note}"

        return FulfillmentResponse(
            success=True,
            order_id=None,
            intent=FulfillmentIntent.FULFILLMENT_PROCEDURE,
            message=full_message,
            procedural_guidance=guidance_text,
            citations=citations,
            information_reliability="procedural_guidance"
        )

    async def handle(self, request: FulfillmentRequest, db: Session) -> FulfillmentResponse:
        try:
            # 1. Order ID Resolution
            order_id = request.order_id
            if not order_id:
                order_id = extract_order_id(request.query)

            # 2. Intent Classification
            intent_result = self.classifier.classify(request.query)
            intent = intent_result.intent
            
            # 3. Handle pure procedural inquiries without requiring an order ID
            if intent == FulfillmentIntent.FULFILLMENT_PROCEDURE and not order_id:
                return self._handle_procedural_query(request.query)

            # If no order ID could be determined for non-procedural queries
            if not order_id:
                return FulfillmentResponse(
                    success=False,
                    order_id=None,
                    intent=intent,
                    message="Please provide a valid order ID (e.g., ORD-1001)."
                )

            # 4. Classify the Query & handle Unknown
            if intent == FulfillmentIntent.UNKNOWN_FULFILLMENT:
                return FulfillmentResponse(
                    success=False,
                    order_id=order_id,
                    intent=intent,
                    message=f"I'm sorry, I could not confidently determine your fulfillment request. Please clarify what you need regarding order {order_id}."
                )

            # 5. Order Lookup
            order = get_order_by_id(db, order_id)
            if not order:
                return FulfillmentResponse(
                    success=False,
                    order_id=order_id,
                    intent=intent,
                    message=f"Order {order_id} was not found in the system."
                )

            GUIDANCE_PATTERN = re.compile(
                r"\b(what should|how should|what to do|what next|what (can|do) (i|we)|what (is|are) (the )?next steps?|"
                r"next steps?|actions?|escalat\w*|procedure|sop|guidance|guide|recommend\w*|resolve|handling)\b",
                re.I
            )
            wants_guidance = bool(GUIDANCE_PATTERN.search(request.query))

            # 6. Intent-Specific Handling
            if intent == FulfillmentIntent.ORDER_STATUS:
                base_message = f"Order {order_id} is currently {order.status}."
                if wants_guidance:
                    query_topic = "order delay handling" if order.status == "delayed" else "order picking and packing procedure"
                    try:
                        hits = self.knowledge_store.query(query_topic, top_k=1) if self.knowledge_store else []
                    except Exception as e:
                        logger.log_event("COMBINED_STATUS_SOP_ERROR", {"error": str(e)})
                        hits = []
                    if hits:
                        citations = self._format_citations(hits)
                        top = hits[0]
                        heading = top.get('heading', '')
                        clean_content = self._clean_sop_content(heading, top.get('content', ''))
                        guidance = f"Standard Operating Guidance ({top.get('sop_id')}) - {heading}:\n{clean_content}"
                        disclaimer = "\n\n⚠️ Note: Procedural guidance is illustrative and requires warehouse supervisor approval."
                        full_msg = f"{base_message}\n\nRecommended Next Steps:\n{guidance}{disclaimer}"
                        return FulfillmentResponse(
                            success=True,
                            order_id=order_id,
                            intent=intent,
                            message=full_msg,
                            procedural_guidance=guidance,
                            citations=citations,
                            information_reliability="combined"
                        )

                return FulfillmentResponse(
                    success=True,
                    order_id=order_id,
                    intent=intent,
                    message=base_message,
                    information_reliability="confirmed_facts"
                )

            elif intent == FulfillmentIntent.ORDER_DELAY:
                if order.status == "delayed":
                    base_message = f"Order {order_id} is currently delayed."

                    delay_reason = getattr(order, "delay_reason", None)
                    carrier_name = getattr(order, "carrier_name", None)
                    revised_date = getattr(order, "revised_delivery_date", None)

                    carrier_detail = ""
                    if isinstance(carrier_name, str) and carrier_name:
                        carrier_detail += f" Carrier: {carrier_name}."
                    if isinstance(revised_date, (date, datetime)):
                        carrier_detail += f" Revised delivery date: {str(revised_date)[:10]}."

                    if isinstance(delay_reason, str) and delay_reason:
                        message = f"{base_message} Reason: {delay_reason}.{carrier_detail}"
                    elif order.sku:
                        try:
                            inv_resp = await self._call_inventory(order.sku, request.user_id, request.role, db, user_plan=request.user_plan)
                            if inv_resp.get("collaboration_blocked") or inv_resp.get("error_code") == "COLLABORATION_REQUIRES_ENTERPRISE":
                                message = f"{base_message} Further cross-agent inventory investigation requires an Enterprise subscription. A specific delay reason is not available in the order record.{carrier_detail}"
                            else:
                                inv_text = inv_resp.get("response", "").lower()
                                inv_items = (inv_resp.get("inventory_details") or {}).get("items", [])
                                qty = None
                                if isinstance(inv_items, list):
                                    for item in inv_items:
                                        if isinstance(item, dict) and item.get("sku") == order.sku:
                                            qty = item.get("quantity_on_hand")
                                            break
                                if isinstance(qty, (int, float)):
                                    is_out_of_stock = (qty == 0)
                                    is_available = (qty > 0)
                                else:
                                    is_out_of_stock = ("out of stock" in inv_text or "stock: 0" in inv_text or "0 units" in inv_text)
                                    is_available = ("stock:" in inv_text or "units on hand" in inv_text or "available" in inv_text)

                                if is_out_of_stock:
                                    message = f"{base_message} The related {order.sku} is currently out of stock. This may be contributing to the delay, but the order record does not contain a specific delay reason.{carrier_detail}"
                                elif is_available:
                                    message = f"{base_message} The related {order.sku} currently has stock available, so the available inventory data does not by itself explain the delay. The order record does not contain a specific delay reason.{carrier_detail}"
                                else:
                                    message = f"{base_message} A specific delay reason is not available in the order record.{carrier_detail}"
                        except Exception as e:
                            logger.log_event("CROSS_AGENT_INVENTORY_ERROR", {"error": str(e), "sku": order.sku})
                            message = f"{base_message} A specific delay reason is not available in the order record.{carrier_detail}"
                    else:
                        message = f"{base_message} A specific delay reason is not available in the order record.{carrier_detail}"

                    # If combined request asks for guidance, retrieve delay SOP guidance
                    if wants_guidance:
                        try:
                            # Search delay handling SOPs
                            hits = self.knowledge_store.query("order delay investigation escalation protocol", top_k=1, category="Order Delays") if self.knowledge_store else []
                            if not hits and self.knowledge_store:
                                hits = self.knowledge_store.query("order delay handling", top_k=1)
                        except Exception as e:
                            logger.log_event("COMBINED_DELAY_SOP_ERROR", {"error": str(e)})
                            hits = []

                        if hits:
                            citations = self._format_citations(hits)
                            top = hits[0]
                            heading = top.get('heading', '')
                            clean_content = self._clean_sop_content(heading, top.get('content', ''))
                            guidance = f"Standard Delay Guidance ({top.get('sop_id')}) - {heading}:\n{clean_content}"
                            disclaimer = "\n\n⚠️ Note: Procedural guidance is illustrative and requires warehouse supervisor approval."
                            full_msg = f"{message}\n\nRecommended Next Steps:\n{guidance}{disclaimer}"
                            return FulfillmentResponse(
                                success=True,
                                order_id=order_id,
                                intent=intent,
                                message=full_msg,
                                procedural_guidance=guidance,
                                citations=citations,
                                information_reliability="combined"
                            )

                    return FulfillmentResponse(
                        success=True,
                        order_id=order_id,
                        intent=intent,
                        message=message,
                        information_reliability="confirmed_facts"
                    )
                else:
                    message = f"Order {order_id} is currently {order.status} and is not marked as delayed."
                    if wants_guidance:
                        try:
                            hits = self.knowledge_store.query("order delay investigation escalation protocol", top_k=1, category="Order Delays") if self.knowledge_store else []
                            if not hits and self.knowledge_store:
                                hits = self.knowledge_store.query("order delay handling", top_k=1)
                        except Exception as e:
                            logger.log_event("COMBINED_DELAY_SOP_ERROR", {"error": str(e)})
                            hits = []

                        if hits:
                            citations = self._format_citations(hits)
                            top = hits[0]
                            heading = top.get('heading', '')
                            clean_content = self._clean_sop_content(heading, top.get('content', ''))
                            guidance = f"Standard Delay Guidance ({top.get('sop_id')}) - {heading}:\n{clean_content}"
                            disclaimer = "\n\n⚠️ Note: Procedural guidance is illustrative and requires warehouse supervisor approval."
                            full_msg = f"{message}\n\nRecommended Next Steps:\n{guidance}{disclaimer}"
                            return FulfillmentResponse(
                                success=True,
                                order_id=order_id,
                                intent=intent,
                                message=full_msg,
                                procedural_guidance=guidance,
                                citations=citations,
                                information_reliability="combined"
                            )

                    return FulfillmentResponse(
                        success=True,
                        order_id=order_id,
                        intent=intent,
                        message=message,
                        information_reliability="confirmed_facts"
                    )

            elif intent == FulfillmentIntent.FULFILLMENT_PROCEDURE:
                proc_resp = self._handle_procedural_query(request.query)
                order_context = f"Order {order_id} is currently {order.status}."
                if order.status == "delayed" and getattr(order, "delay_reason", None):
                    order_context += f" Reason: {order.delay_reason}."
                carrier_name = getattr(order, "carrier_name", None)
                if carrier_name:
                    order_context += f" Carrier: {carrier_name}."
                revised_date = getattr(order, "revised_delivery_date", None)
                if revised_date:
                    order_context += f" Revised delivery date: {str(revised_date)[:10]}."

                combined_msg = f"{order_context}\n\nRecommended Next Steps:\n{proc_resp.message}"
                return FulfillmentResponse(
                    success=True,
                    order_id=order_id,
                    intent=intent,
                    message=combined_msg,
                    procedural_guidance=proc_resp.procedural_guidance,
                    citations=proc_resp.citations,
                    information_reliability="combined"
                )


            elif intent == FulfillmentIntent.ORDER_DETAILS:
                message = (
                    f"Details for {order_id}:\n"
                    f"- Customer: {order.customer_name}\n"
                    f"- SKU: {order.sku}\n"
                    f"- Quantity: {order.quantity}\n"
                    f"- Status: {order.status}\n"
                    f"- Created At: {order.created_at}"
                )
                return FulfillmentResponse(success=True, order_id=order_id, intent=intent, message=message)

            elif intent == FulfillmentIntent.SHIPPING_STATUS:
                if order.status == "shipped":
                    message = f"Order {order_id} is marked as shipped."
                else:
                    message = f"Order {order_id} is currently {order.status} and is not marked as shipped."
                return FulfillmentResponse(success=True, order_id=order_id, intent=intent, message=message)

            elif intent == FulfillmentIntent.FULFILLMENT_PROGRESS:
                if order.status == "shipped":
                    message = f"Order {order_id} is marked as shipped. Detailed intermediate fulfillment stage data is not available."
                else:
                    message = f"Order {order_id} is currently {order.status}. Detailed picking, packing, and dispatch progress is not available in the current order data."
                return FulfillmentResponse(success=True, order_id=order_id, intent=intent, message=message)

            # Safety fallback for unexpected enums
            return FulfillmentResponse(
                success=False,
                order_id=order_id,
                intent=intent,
                message="Unable to process the fulfillment request at this time."
            )

        except Exception as e:
            logger.log_event("FULFILLMENT_AGENT_EXCEPTION", {"error": str(e), "query": request.query})
            return FulfillmentResponse(
                success=False,
                order_id=request.order_id if request else None,
                intent=None,
                message="Unable to process the fulfillment request at this time."
            )

fulfillment_agent = FulfillmentAgent()
