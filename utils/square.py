from typing import Optional
from square.client import Client
from square.http.api_response import ApiResponse
import logging
from config import SQUARE_ACCESS_TOKEN, SQUARE_ENVIRONMENT
import uuid

logger = logging.getLogger(__name__)

# Initialize Square client
square_client = Client(
    access_token=SQUARE_ACCESS_TOKEN,
    environment=SQUARE_ENVIRONMENT
)

def format_money_amount(amount: float) -> int:
    """Convert dollar amount to cents for Square API"""
    return int(amount * 100)

def check_connection() -> bool:
    """Test Square API connection"""
    try:
        response = square_client.locations.list_locations()
        return response.is_success()
    except Exception as e:
        logger.error(f"Square connection test failed: {str(e)}")
        return False

def process_card_payment(amount: float, source_id: str, location_id: str) -> dict:
    """Process a card payment"""
    try:
        body = {
            "source_id": source_id,
            "amount_money": {
                "amount": format_money_amount(amount),
                "currency": "USD"
            },
            "idempotency_key": str(uuid.uuid4())
        }
        
        response = square_client.payments.create_payment(body)
        if response.is_success():
            return {
                "success": True,
                "payment_id": response.body["payment"]["id"],
                "status": response.body["payment"]["status"]
            }
        else:
            logger.error(f"Payment failed: {response.errors}")
            return {
                "success": False,
                "error": response.errors
            }
    except Exception as e:
        logger.error(f"Payment processing error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def process_refund(payment_id: str, amount: Optional[float] = None) -> dict:
    """Process a refund for a payment"""
    try:
        body = {
            "idempotency_key": str(uuid.uuid4()),
            "payment_id": payment_id
        }
        
        if amount:
            body["amount_money"] = {
                "amount": format_money_amount(amount),
                "currency": "USD"
            }
            
        response = square_client.refunds.refund_payment(body)
        if response.is_success():
            return {
                "success": True,
                "refund_id": response.body["refund"]["id"],
                "status": response.body["refund"]["status"]
            }
        else:
            logger.error(f"Refund failed: {response.errors}")
            return {
                "success": False,
                "error": response.errors
            }
    except Exception as e:
        logger.error(f"Refund processing error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def get_payment_status(payment_id: str) -> dict:
    """Get the status of a payment"""
    try:
        response = square_client.payments.get_payment(payment_id)
        if response.is_success():
            return {
                "success": True,
                "status": response.body["payment"]["status"]
            }
        else:
            logger.error(f"Get payment status failed: {response.errors}")
            return {
                "success": False,
                "error": response.errors
            }
    except Exception as e:
        logger.error(f"Get payment status error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        } 