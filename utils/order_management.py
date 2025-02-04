from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Order, OrderHistory, OrderStatus
import logging

logger = logging.getLogger(__name__)

def reset_order_numbers(db: Session) -> bool:
    """
    Manually reset order numbers.
    Archives all completed orders before resetting.
    """
    try:
        # Archive all completed orders first
        archive_completed_orders(db)
        
        # Get all active orders
        active_orders = db.query(Order).filter(
            Order.status.in_([OrderStatus.PREP, OrderStatus.READY])
        ).order_by(Order.created_at).all()
        
        # Reset their order numbers starting from 1
        for i, order in enumerate(active_orders, 1):
            order.order_number = i
        
        db.commit()
        logger.info("Order numbers reset successfully")
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to reset order numbers: {e}")
        return False

def validate_order_number(db: Session, order_number: int) -> bool:
    """
    Validate that an order number is not already in use for active orders.
    """
    existing_order = db.query(Order).filter(
        Order.order_number == order_number,
        Order.status.in_([OrderStatus.PREP, OrderStatus.READY])
    ).first()
    
    return existing_order is None

def archive_completed_orders(db: Session) -> int:
    """
    Archive orders that are completed (DONE, VOID, REFUNDED, PARTIALLY_REFUNDED)
    and older than 24 hours.
    Returns the number of orders archived.
    """
    try:
        # Get orders to archive
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        completed_orders = db.query(Order).filter(
            Order.status.in_([
                OrderStatus.DONE,
                OrderStatus.VOID,
                OrderStatus.REFUNDED,
                OrderStatus.PARTIALLY_REFUNDED
            ]),
            Order.created_at < cutoff_time
        ).all()
        
        # Create archive records
        archived_count = 0
        for order in completed_orders:
            archive = OrderHistory.from_order(order)
            db.add(archive)
            archived_count += 1
        
        # Delete archived orders from main table
        if archived_count > 0:
            for order in completed_orders:
                db.delete(order)
            
            db.commit()
            logger.info(f"Archived {archived_count} completed orders")
        
        return archived_count
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to archive orders: {e}")
        return 0

def daily_order_cleanup(db: Session) -> bool:
    """
    Perform daily order cleanup:
    1. Archive completed orders
    2. Reset order numbers for active orders
    """
    try:
        # Archive old orders first
        archive_completed_orders(db)
        
        # Reset order numbers for remaining active orders
        reset_order_numbers(db)
        
        logger.info("Daily order cleanup completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to perform daily order cleanup: {e}")
        return False 