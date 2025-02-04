from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime, timedelta

from models import (
    Staff, Order, OrderItem, Item, Discount, CardFee,
    OrderStatus, PaymentMethod, get_db
)
from utils.auth import get_current_staff
from utils.order_validation import (
    get_next_order_number,
    calculate_order_totals,
    validate_order_items,
    validate_payment
)
from utils.websocket import manager
from Printer.printer import send_to_physical_printer, send_to_kds, print_receipt
from utils.order_management import validate_order_number

router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized"},
        404: {"description": "Order not found"},
        422: {"description": "Validation error"}
    }
)

# Pydantic models
class ModifierData(BaseModel):
    """Modifier selection data"""
    mod_list_id: int = Field(..., description="ID of the modifier list")
    mod_id: int = Field(..., description="ID of the selected modifier")

    class Config:
        json_schema_extra = {
            "example": {
                "mod_list_id": 1,
                "mod_id": 1
            }
        }

class OrderItemData(BaseModel):
    """Order item data"""
    item_id: int = Field(..., description="Menu item ID")
    quantity: int = Field(..., gt=0, description="Number of items")
    mods: List[ModifierData] = Field(default=[], description="Selected modifiers")

    class Config:
        json_schema_extra = {
            "example": {
                "item_id": 1,
                "quantity": 1,
                "mods": [
                    {
                        "mod_list_id": 1,
                        "mod_id": 1
                    }
                ]
            }
        }

class OrderCreate(BaseModel):
    """Order creation data"""
    items: List[OrderItemData] = Field(..., description="Items to order")

    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "item_id": 1,
                        "quantity": 1,
                        "mods": [
                            {
                                "mod_list_id": 1,
                                "mod_id": 1
                            }
                        ]
                    }
                ]
            }
        }

class OrderUpdate(BaseModel):
    """Order update model"""
    status: Optional[OrderStatus] = Field(None, description="New order status")
    notes: Optional[str] = Field(None, description="Order notes")
    payment_method: Optional[PaymentMethod] = Field(None, description="Payment method")
    tip_amount: Optional[float] = Field(
        None,
        ge=0,
        description="Tip amount in dollars"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "ready",
                "notes": "Extra napkins please",
                "payment_method": "card",
                "tip_amount": 5.00
            }
        }

class PaymentData(BaseModel):
    """Payment data model"""
    payment_method: PaymentMethod = Field(..., description="Payment method (CASH/CARD)")
    cash_tendered: Optional[float] = Field(
        None,
        ge=0,
        description="Amount of cash received (required for CASH payment)"
    )
    tip_amount: Optional[float] = Field(
        default=0.0,
        ge=0,
        description="Tip amount in dollars"
    )
    card_fee_id: Optional[int] = Field(
        None,
        description="ID of the card fee to apply (required for CARD payment)"
    )

    @validator('cash_tendered')
    def validate_cash_payment(cls, v, values):
        if values.get('payment_method') == PaymentMethod.CASH and v is None:
            raise ValueError('cash_tendered is required for cash payments')
        return v

    @validator('card_fee_id')
    def validate_card_payment(cls, v, values):
        if values.get('payment_method') == PaymentMethod.CARD and v is None:
            raise ValueError('card_fee_id is required for card payments')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "payment_method": "CARD",
                "tip_amount": 5.00,
                "card_fee_id": 1
            }
        }

# Routes
@router.get(
    "",
    response_model=List[dict],
    summary="List Orders",
    response_description="List of orders"
)
async def list_orders(
    status: Optional[str] = None,
    date: Optional[str] = None,
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """List orders with optional filters"""
    query = db.query(Order)
    
    if status:
        query = query.filter(Order.status == status)
    
    if date:
        try:
            filter_date = datetime.strptime(date, "%Y-%m-%d")
            query = query.filter(
                Order.created_at >= filter_date,
                Order.created_at < filter_date + timedelta(days=1)
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    orders = query.all()
    return [order.to_dict() for order in orders]

@router.post(
    "",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create Order",
    response_description="Created order details"
)
async def create_order(
    order_data: OrderCreate,
    background_tasks: BackgroundTasks,
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """Create a new order"""
    try:
        # Validate items and modifiers
        validate_order_items(db, [item.dict() for item in order_data.items])
        
        # Get next order number
        order_number = get_next_order_number(db)
        
        # Create order
        order = Order(
            order_number=order_number,
            staff_id=current_staff.id,
            status=OrderStatus.PREP
        )
        db.add(order)
        db.flush()
        
        # Add items
        for item_data in order_data.items:
            item = db.query(Item).get(item_data.item_id)
            if not item:
                raise HTTPException(status_code=404, detail=f"Item {item_data.item_id} not found")
            
            order_item = OrderItem(
                order_id=order.id,
                item_id=item_data.item_id,
                quantity=item_data.quantity
            )
            db.add(order_item)
        
        db.commit()
        db.refresh(order)
        
        # Send to kitchen display and printer
        background_tasks.add_task(send_to_physical_printer, order.id)
        background_tasks.add_task(send_to_kds, order.id)
        
        # Broadcast update
        await manager.broadcast_order_update(order.id, "created")
        
        return order.to_dict()
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/{order_id}",
    response_model=dict,
    summary="Get Order",
    response_description="Order details"
)
async def get_order(order_id: int, db: Session = Depends(get_db)):
    """
    Get details of a specific order.

    Parameters:
    - order_id: ID of the order to retrieve

    Returns:
    - Order details including:
      - Order number
      - Items and modifiers
      - Totals
      - Status

    Raises:
    - 401: Not authenticated
    - 404: Order not found
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order.to_dict()

@router.post(
    "/{order_id}/items",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Add Item to Order",
    response_description="Updated order details"
)
async def add_item(
    order_id: int,
    item: OrderItemData,
    background_tasks: BackgroundTasks,
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """
    Add an item to an existing order.

    Can only add items to orders with OPEN status.
    Automatically updates order totals.
    Sends updates to kitchen display.

    Parameters:
    - order_id: ID of the order
    - item: Item to add with:
      - item_id: Menu item ID
      - quantity: Number of items
      - mods: Selected modifiers (optional)

    Returns:
    - Updated order details

    Raises:
    - 400: Order not open or invalid item
    - 401: Not authenticated
    - 404: Order or item not found
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status != OrderStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only add items to open orders"
        )
    
    try:
        # Validate item and modifiers
        validate_order_items(db, [item.dict()])
        
        # Get item for price snapshot
        db_item = db.query(Item).get(item.item_id)
        
        # Add item
        order_item = OrderItem(
            order_id=order.id,
            item_id=item.item_id,
            quantity=item.quantity,
            price_each=db_item.price,
            modifiers=[mod.dict() for mod in item.mods]
        )
        db.add(order_item)
        
        # Recalculate totals
        totals = calculate_order_totals(
            db, order,
            discount_id=order.discount_id,
            card_fee_id=order.card_fee_id,
            tip_amount=order.tip_amount
        )
        
        # Update order totals
        for key, value in totals.items():
            setattr(order, key, value)
        
        db.commit()
        db.refresh(order)
        
        # Broadcast order update
        order_dict = order.to_dict()
        await manager.broadcast_order_update(order_dict)
        
        # Send update to KDS
        background_tasks.add_task(
            send_to_kds,
            order.order_number,
            [item.dict() for item in order.items]
        )
        
        return order_dict
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete(
    "/{order_id}/items/{item_id}",
    response_model=dict,
    summary="Remove Item from Order",
    response_description="Updated order details"
)
async def remove_item(
    order_id: int,
    item_id: int,
    background_tasks: BackgroundTasks,
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """
    Remove an item from an order.

    Can only remove items from orders with OPEN status.
    Automatically updates order totals.
    Sends updates to kitchen display.

    Parameters:
    - order_id: ID of the order
    - item_id: ID of the item to remove

    Returns:
    - Updated order details

    Raises:
    - 400: Order not open
    - 401: Not authenticated
    - 404: Order or item not found
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status != OrderStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only remove items from open orders"
        )
    
    item = db.query(OrderItem).filter(
        OrderItem.order_id == order_id,
        OrderItem.id == item_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in order")
    
    db.delete(item)
    
    # Recalculate totals
    totals = calculate_order_totals(
        db, order,
        discount_id=order.discount_id,
        card_fee_id=order.card_fee_id,
        tip_amount=order.tip_amount
    )
    
    # Update order totals
    for key, value in totals.items():
        setattr(order, key, value)
    
    db.commit()
    db.refresh(order)
    
    # Broadcast order update
    order_dict = order.to_dict()
    await manager.broadcast_order_update(order_dict)
    
    # Send update to KDS
    background_tasks.add_task(
        send_to_kds,
        order.order_number,
        [item.dict() for item in order.items]
    )
    
    return order_dict

@router.put("/{order_id}", response_model=dict)
async def update_order(
    order_id: int,
    order_data: OrderUpdate,
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """Update order details (discount, card fee, tip)"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status != OrderStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only update open orders"
        )
    
    # Update fields and recalculate totals
    if order_data.discount_id is not None:
        order.discount_id = order_data.discount_id
    if order_data.card_fee_id is not None:
        order.card_fee_id = order_data.card_fee_id
    if order_data.tip_amount is not None:
        order.tip_amount = order_data.tip_amount
    
    totals = calculate_order_totals(
        db, order,
        discount_id=order.discount_id,
        card_fee_id=order.card_fee_id,
        tip_amount=order.tip_amount
    )
    
    # Update order totals
    for key, value in totals.items():
        setattr(order, key, value)
    
    db.commit()
    db.refresh(order)
    
    # Broadcast order update
    order_dict = order.to_dict()
    await manager.broadcast_order_update(order_dict)
    
    return order_dict

@router.post("/{order_id}/close", response_model=dict)
async def close_order(
    order_id: int,
    payment_data: PaymentData,
    background_tasks: BackgroundTasks,
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """Close an order with payment"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status != OrderStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order must be READY to close"
        )
    
    try:
        # Update payment method and calculate card fee if needed
        order.payment_method = payment_data.payment_method
        if payment_data.payment_method == PaymentMethod.CARD:
            order.calculate_card_fee(db)
        
        # Update tip if provided
        if payment_data.tip_amount:
            order.tip_amount = payment_data.tip_amount
        
        # Recalculate final total
        order.calculate_total(db)
        
        # Validate payment and calculate change for cash payments
        if payment_data.payment_method == PaymentMethod.CASH:
            change = validate_payment(
                payment_data.payment_method,
                order.total,
                payment_data.cash_tendered
            )
            order.cash_tendered = payment_data.cash_tendered
            order.cash_change = change
        
        # Update order status and timing
        order.status = OrderStatus.DONE
        order.done_at = datetime.utcnow()
        
        db.commit()
        db.refresh(order)
        
        # Broadcast order update
        order_dict = order.to_dict()
        await manager.broadcast_order_update(order_dict)
        
        # Print receipt in background
        background_tasks.add_task(
            print_receipt,
            order.order_number,
            [item.to_dict() for item in order.items],
            order.subtotal,
            order.tax,
            order.total,
            order.payment_method,
            order.card_fee,
            order.cash_tendered if order.payment_method == PaymentMethod.CASH else None,
            order.cash_change if order.payment_method == PaymentMethod.CASH else None
        )
        
        return order_dict
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post(
    "/{order_id}/discounts/{discount_id}",
    response_model=dict,
    summary="Apply Discount",
    response_description="Updated order with applied discount"
)
async def apply_discount(
    order_id: int,
    discount_id: int,
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """Apply a discount to an order"""
    # Get order
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Get discount
    discount = db.query(Discount).filter(Discount.id == discount_id).first()
    if not discount:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discount not found"
        )
    
    # Apply discount
    if not order.apply_discount(discount, db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to apply discount"
        )
    
    db.commit()
    db.refresh(order)
    return order.to_dict()

@router.delete(
    "/{order_id}/discounts/{discount_id}",
    response_model=dict,
    summary="Remove Discount",
    response_description="Updated order after removing discount"
)
async def remove_discount(
    order_id: int,
    discount_id: int,
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """Remove a discount from an order"""
    # Get order
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Find and remove the discount
    order_discount = db.query(OrderDiscount).filter(
        OrderDiscount.order_id == order_id,
        OrderDiscount.discount_id == discount_id
    ).first()
    
    if not order_discount:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discount not found on this order"
        )
    
    # Remove discount
    db.delete(order_discount)
    
    # Recalculate order total
    order.calculate_total(db)
    
    db.commit()
    db.refresh(order)
    return order.to_dict()

@router.patch(
    "/{order_id}",
    response_model=dict,
    summary="Update Order",
    response_description="Updated order details"
)
async def update_order_status(
    order_id: int,
    status: Optional[str] = None,
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """Update order status"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if status:
        # Validate status transition
        valid_transitions = {
            OrderStatus.PREP: [OrderStatus.READY, OrderStatus.CANCELLED],
            OrderStatus.READY: [OrderStatus.DONE],
            OrderStatus.DONE: [],  # No transitions allowed from DONE
            OrderStatus.CANCELLED: [],  # No transitions allowed from CANCELLED
            OrderStatus.REFUNDED: [],  # No transitions allowed from REFUNDED
            OrderStatus.PARTIALLY_REFUNDED: []  # No transitions allowed from PARTIALLY_REFUNDED
        }
        
        if status not in [s.value for s in OrderStatus]:
            raise HTTPException(status_code=400, detail="Invalid status")
            
        new_status = OrderStatus(status)
        if new_status not in valid_transitions.get(order.status, []):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status transition from {order.status} to {new_status}"
            )
        
        order.status = new_status
        if new_status == OrderStatus.DONE:
            order.done_at = datetime.utcnow()
        elif new_status == OrderStatus.CANCELLED:
            order.cancelled_at = datetime.utcnow()
        
        db.commit()
        db.refresh(order)
        
        # Broadcast update
        await manager.broadcast_order_update(order.id, status)
    
    return order.to_dict()

@router.post(
    "/{order_id}/cancel",
    response_model=dict,
    summary="Cancel Order",
    response_description="Cancelled order details"
)
async def cancel_order(
    order_id: int,
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """Cancel an open order"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status != OrderStatus.PREP:
        raise HTTPException(status_code=400, detail="Can only cancel orders in PREP status")
    
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = datetime.utcnow()
    db.commit()
    
    # Broadcast update
    await manager.broadcast_order_update(order.id, "cancelled")
    
    return order.to_dict() 