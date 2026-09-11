from sqlalchemy.orm import Session
from agents.fulfillment.schemas import FulfillmentRequest, FulfillmentResponse, FulfillmentIntent
from agents.fulfillment.extractor import extract_order_id
from agents.fulfillment.order_service import get_order_by_id
from agents.fulfillment.intent_classifier import FulfillmentIntentClassifier, fulfillment_intent_classifier
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

class FulfillmentAgent:
    def __init__(self, classifier: FulfillmentIntentClassifier = None):
        self.classifier = classifier or fulfillment_intent_classifier

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
                    message = f"Order {order_id} is currently delayed. A specific delay reason is not available in the order record."
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
