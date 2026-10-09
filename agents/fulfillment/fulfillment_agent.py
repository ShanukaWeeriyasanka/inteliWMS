from datetime import date, datetime
from typing import Optional
from sqlalchemy.orm import Session
from agents.fulfillment.schemas import FulfillmentRequest, FulfillmentResponse, FulfillmentIntent
from agents.fulfillment.extractor import extract_order_id
from agents.fulfillment.order_service import get_order_by_id
from agents.fulfillment.intent_classifier import FulfillmentIntentClassifier, fulfillment_intent_classifier
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

class FulfillmentAgent:
    def __init__(self, classifier: FulfillmentIntentClassifier = None, dispatcher=None):
        self.classifier = classifier or fulfillment_intent_classifier
        self.dispatcher = dispatcher

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

    async def handle(self, request: FulfillmentRequest, db: Session) -> FulfillmentResponse:
        try:
            # 1. Order ID Resolution
            order_id = request.order_id
            if not order_id:
                order_id = extract_order_id(request.query)

            # 2. Intent Classification
            intent_result = self.classifier.classify(request.query)
            intent = intent_result.intent
            
            # If no order ID could be determined
            if not order_id:
                return FulfillmentResponse(
                    success=False,
                    order_id=None,
                    intent=intent,
                    message="Please provide a valid order ID."
                )

            # 3. Classify the Query & handle Unknown
            if intent == FulfillmentIntent.UNKNOWN_FULFILLMENT:
                return FulfillmentResponse(
                    success=False,
                    order_id=order_id,
                    intent=intent,
                    message=f"I'm sorry, I could not confidently determine your fulfillment request. Please clarify what you need regarding order {order_id}."
                )

            # 4. Order Lookup
            order = get_order_by_id(db, order_id)
            if not order:
                return FulfillmentResponse(
                    success=False,
                    order_id=order_id,
                    intent=intent,
                    message=f"Order {order_id} was not found in the system."
                )

            # 5. Intent-Specific Handling
            if intent == FulfillmentIntent.ORDER_STATUS:
                message = f"Order {order_id} is currently {order.status}."
                return FulfillmentResponse(success=True, order_id=order_id, intent=intent, message=message)

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
                                return FulfillmentResponse(success=True, order_id=order_id, intent=intent, message=message)

                            inv_text = inv_resp.get("response", "").lower()

                            # Check structured inventory details first if present
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
                                is_out_of_stock = (
                                    "out of stock" in inv_text
                                    or "stock: 0" in inv_text
                                    or "0 units" in inv_text
                                )
                                is_available = (
                                    "stock:" in inv_text
                                    or "units on hand" in inv_text
                                    or "available" in inv_text
                                )

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
                else:
                    message = f"Order {order_id} is currently {order.status} and is not marked as delayed."
                return FulfillmentResponse(success=True, order_id=order_id, intent=intent, message=message)


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
