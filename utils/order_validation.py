from typing import Optional
from sqlalchemy.orm import Session
from models import Order, OrderItem, Item, Discount, CardFee
from datetime import datetime

def get_next_order_number(db: Session) -> int:
    """Get the next available order number (1-99)"""
    # Get the last order number used today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    last_order = db.query(Order).filter(
        Order.created_at >= today_start
    ).order_by(Order.order_number.desc()).first()
    
    if not last_order:
        return 1
    
    next_number = last_order.order_number + 1
    return 1 if next_number > 99 else next_number

def calculate_order_totals(
    db: Session,
    order: Order,
    discount_id: Optional[int] = None,
    card_fee_id: Optional[int] = None,
    tip_amount: float = 0.0
) -> dict:
    """Calculate order totals including subtotal, discount, card fee, and final total"""
    # Calculate subtotal from items
    subtotal = sum(item.calculate_subtotal() for item in order.items)
    
    # Apply discount if any
    discount_amount = 0.0
    if discount_id:
        discount = db.query(Discount).filter(
            Discount.id == discount_id,
            Discount.active == True
        ).first()
        if discount:
            if discount.discount_type == "percentage":
                discount_amount = subtotal * (discount.amount / 100)
            else:  # flat amount
                discount_amount = discount.amount
    
    # Calculate total after discount
    total_after_discount = subtotal - discount_amount
    
    # Apply card fee if any
    card_fee_amount = 0.0
    if card_fee_id:
        card_fee = db.query(CardFee).filter(
            CardFee.id == card_fee_id,
            CardFee.active == True
        ).first()
        if card_fee:
            card_fee_amount = (total_after_discount * (card_fee.percentage / 100)) + card_fee.flat_amount
    
    # Calculate final total
    final_total = total_after_discount + card_fee_amount + tip_amount
    
    return {
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "total_after_discount": total_after_discount,
        "card_fee_amount": card_fee_amount,
        "tip_amount": tip_amount,
        "total": final_total
    }

def validate_order_items(db: Session, items_data: list) -> None:
    """Validate order items and their modifiers"""
    for item_data in items_data:
        # Check if item exists and is active
        item = db.query(Item).filter(
            Item.id == item_data["item_id"],
            Item.active == True
        ).first()
        if not item:
            raise ValueError(f"Item {item_data['item_id']} not found or inactive")
        
        # Validate quantity
        if item_data["quantity"] < 1:
            raise ValueError("Quantity must be at least 1")
        
        # Validate modifiers if any
        if "modifiers" in item_data:
            mod_lists = {ml.id: ml for ml in item.mod_lists}
            
            # Track selections per mod list
            selections = {}
            
            for mod in item_data["modifiers"]:
                mod_list = mod_lists.get(mod["mod_list_id"])
                if not mod_list:
                    raise ValueError(f"Modifier list {mod['mod_list_id']} not found")
                
                # Count selections for this mod list
                selections[mod_list.id] = selections.get(mod_list.id, 0) + 1
                
                # Validate modifier exists in the list
                valid_mod = any(m.id == mod["mod_id"] for m in mod_list.mods)
                if not valid_mod:
                    raise ValueError(f"Invalid modifier {mod['mod_id']} for list {mod_list.id}")
            
            # Check min/max selections for each mod list
            for mod_list in item.mod_lists:
                count = selections.get(mod_list.id, 0)
                if count < mod_list.min_selections:
                    raise ValueError(
                        f"Item {item.name} requires at least {mod_list.min_selections} "
                        f"selections from {mod_list.name}"
                    )
                if mod_list.max_selections and count > mod_list.max_selections:
                    raise ValueError(
                        f"Item {item.name} allows at most {mod_list.max_selections} "
                        f"selections from {mod_list.name}"
                    )

def validate_payment(
    payment_method: str,
    total: float,
    cash_tendered: Optional[float] = None
) -> float:
    """Validate payment details and calculate change if needed"""
    if payment_method == "cash":
        if cash_tendered is None:
            raise ValueError("Cash tendered amount is required for cash payments")
        if cash_tendered < total:
            raise ValueError("Insufficient cash tendered")
        return cash_tendered - total
    elif payment_method == "card":
        if cash_tendered is not None:
            raise ValueError("Cash tendered should not be provided for card payments")
        return 0.0
    else:
        raise ValueError("Invalid payment method") 