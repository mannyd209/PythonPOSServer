from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

from models import Staff, Order, OrderStatus, PaymentMethod, get_db
from models.system import CardFeeSettings
from utils.auth import get_current_staff
from utils.square import process_card_payment, process_refund, get_payment_status, check_connection
from utils.order_validation import calculate_order_totals
from utils.websocket import manager
from utils.network import network_manager
from Printer.printer import print_receipt

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized"},
        404: {"description": "Order not found"},
        422: {"description": "Validation error"}
    }
)

class PaymentRequest(BaseModel):
    """Payment request model"""
    order_id: int = Field(..., description="ID of the order to process payment for")
    amount: float = Field(..., ge=0, description="Payment amount in dollars")
    payment_method: str = Field(..., description="Payment method (card/cash)")
    payment_details: dict = Field(..., description="Payment-specific details")

    class Config:
        json_schema_extra = {
            "example": {
                "order_id": 1,
                "amount": 25.99,
                "payment_method": "card",
                "payment_details": {
                    "source_id": "cnon:card-nonce-ok",
                    "tip_amount": 5.00
                }
            }
        }

class RefundRequest(BaseModel):
    """Refund request model"""
    order_id: int = Field(..., description="ID of the order to refund")
    amount: float = Field(..., ge=0, description="Amount to refund in dollars")
    reason: str = Field(..., description="Reason for the refund")

    class Config:
        json_schema_extra = {
            "example": {
                "order_id": 1,
                "amount": 25.99,
                "reason": "Customer dissatisfaction"
            }
        }

@router.post(
    "/process",
    response_model=dict,
    summary="Process Payment",
    response_description="Payment processing result"
)
async def process_payment(
    payment: PaymentRequest,
    background_tasks: BackgroundTasks,
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """Process a payment for an order"""
    order = db.query(Order).filter(Order.id == payment.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status == OrderStatus.DONE:
        raise HTTPException(
            status_code=400,
            detail="Order is already paid"
        )

    try:
        if payment.payment_method == "card":
            # Enable internet for card payment
            if not await network_manager.enable_internet():
                raise HTTPException(
                    status_code=503,
                    detail="Failed to establish internet connection"
                )

            try:
                # Process card payment
                payment_result = await process_card_payment(
                    source_id=payment.payment_details["source_id"],
                    amount=int(payment.amount * 100),  # Convert to cents
                    order_id=str(order.id),
                    order_number=order.order_number
                )

                if payment_result["status"] == "success":
                    order.payment_method = PaymentMethod.CARD
                    order.status = OrderStatus.DONE
                    order.done_at = datetime.utcnow()
                    order.square_payment_id = payment_result["payment_id"]
                    
                    if "tip_amount" in payment.payment_details:
                        order.tip_amount = payment.payment_details["tip_amount"]
                    
                    db.commit()
                    
                    # Schedule receipt printing
                    background_tasks.add_task(print_receipt, order.id)
                    await manager.broadcast_order_update(order.id, "done")
                    
                    return {
                        "success": True,
                        "message": "Payment processed successfully",
                        "payment_id": payment_result["payment_id"],
                        "order": order.to_dict()
                    }
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=payment_result.get("error", "Payment failed")
                    )

            finally:
                # Disable internet after transaction
                await network_manager.disable_internet()

        elif payment.payment_method == "cash":
            if "cash_tendered" not in payment.payment_details:
                raise HTTPException(
                    status_code=400,
                    detail="Cash tendered amount is required"
                )

            cash_tendered = payment.payment_details["cash_tendered"]
            if cash_tendered < payment.amount:
                raise HTTPException(
                    status_code=400,
                    detail="Insufficient cash tendered"
                )

            order.payment_method = PaymentMethod.CASH
            order.status = OrderStatus.DONE
            order.done_at = datetime.utcnow()
            order.cash_tendered = cash_tendered
            order.cash_change = cash_tendered - payment.amount

            if "tip_amount" in payment.payment_details:
                order.tip_amount = payment.payment_details["tip_amount"]

            db.commit()

            # Schedule receipt printing
            background_tasks.add_task(print_receipt, order.id)
            await manager.broadcast_order_update(order.id, "done")

            return {
                "success": True,
                "message": "Cash payment processed successfully",
                "order": order.to_dict()
            }

        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid payment method"
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.post(
    "/{payment_id}/refund",
    response_model=dict,
    summary="Process Refund",
    response_description="Refund processing result"
)
async def process_refund(
    payment_id: str,
    refund: RefundRequest,
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """Process a refund"""
    if not current_staff.isAdmin:
        raise HTTPException(
            status_code=403,
            detail="Only admins can process refunds"
        )

    order = db.query(Order).filter(Order.id == refund.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status not in [OrderStatus.DONE, OrderStatus.PARTIALLY_REFUNDED]:
        raise HTTPException(
            status_code=400,
            detail="Order must be completed to process refund"
        )

    try:
        # Enable internet for refund processing
        if not await network_manager.enable_internet():
            raise HTTPException(
                status_code=503,
                detail="Failed to establish internet connection"
            )

        try:
            refund_result = await process_refund(
                payment_id=payment_id,
                amount=refund.amount,
                reason=refund.reason
            )

            if refund_result["status"] == "success":
                order.status = OrderStatus.REFUNDED if refund.amount >= order.total else OrderStatus.PARTIALLY_REFUNDED
                order.refunded_at = datetime.utcnow()
                order.refund_amount = refund.amount
                order.refund_reason = refund.reason
                
                db.commit()
                
                await manager.broadcast_order_update(order.id, order.status.value)
                
                return {
                    "success": True,
                    "refund_id": refund_result["refund_id"],
                    "order": order.to_dict()
                }
            else:
                raise HTTPException(
                    status_code=400,
                    detail=refund_result.get("error", "Refund failed")
                )

        finally:
            # Disable internet after transaction
            await network_manager.disable_internet()

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.get(
    "/status/{payment_id}",
    response_model=dict,
    summary="Get Payment Status",
    response_description="Current payment status"
)
async def get_payment_status(
    payment_id: str,
    current_staff: Staff = Depends(get_current_staff)
):
    """Get the current status of a payment"""
    try:
        status_result = await get_payment_status(payment_id)
        return {
            "success": True,
            "status": status_result["status"],
            "receipt_url": status_result.get("receipt_url"),
            "card_details": status_result.get("card_details")
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        ) 