from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from datetime import datetime
from .base import Base
from .system import CardFeeSettings

class OrderStatus(str, enum.Enum):
    PREP = "prep"      # Order is being prepared
    READY = "ready"    # Order is ready for pickup/delivery
    DONE = "done"      # Order is completed and paid for
    VOID = "void"      # Order has been voided/cancelled
    REFUNDED = "refunded"  # Order has been fully refunded
    PARTIALLY_REFUNDED = "partially_refunded"  # Order has been partially refunded

class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    CARD = "card"

class Order(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_number = Column(Integer, nullable=False)  # 1-99 cycling number
    staff_id = Column(Integer, ForeignKey('staff.id'), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.PREP)
    
    # Price calculations
    subtotal = Column(Float, nullable=False)
    tax = Column(Float, nullable=False)
    card_fee = Column(Float, default=0.00)  # Only applied for card payments
    total = Column(Float, nullable=False)    # subtotal - discount_amount + tax + card_fee
    
    payment_method = Column(Enum(PaymentMethod))
    notes = Column(String)
    
    # Square payment details
    square_payment_id = Column(String)
    square_refund_id = Column(String)
    
    # Timing tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ready_at = Column(DateTime(timezone=True))    # Set when status = READY
    done_at = Column(DateTime(timezone=True))     # Set when status = DONE
    refunded_at = Column(DateTime(timezone=True)) # Set when refunded

    # Relationships
    staff = relationship("Staff", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    discounts = relationship("OrderDiscount", back_populates="order", cascade="all, delete-orphan")

    def calculate_card_fee(self, db_session):
        """Calculate card fee based on admin settings"""
        if self.payment_method == PaymentMethod.CARD:
            # Get card fee settings
            settings = db_session.query(CardFeeSettings).first()
            
            if settings and settings.available:
                # Calculate base amount (subtotal - discount + tax)
                base_amount = self.subtotal - self.get_total_discount() + self.tax
                # Calculate fee (percentage or minimum, whichever is higher)
                calculated_fee = max(
                    base_amount * settings.percentage_amount, 
                    settings.min_fee
                )
                self.card_fee = round(calculated_fee, 2)
            else:
                self.card_fee = 0.00
        else:
            self.card_fee = 0.00

    def get_total_discount(self) -> float:
        """Get total discount amount applied to the order"""
        return sum(d.amount_applied for d in self.discounts)

    def calculate_total(self, db_session):
        """Calculate final total including discounts, tax, and card fee if applicable"""
        # Calculate total discount
        total_discount = self.get_total_discount()
        
        # Calculate base total
        base_total = self.subtotal - total_discount + self.tax
        
        # Calculate and add card fee if applicable
        self.calculate_card_fee(db_session)
        
        # Set final total
        self.total = round(base_total + self.card_fee, 2)

    def apply_discount(self, discount, db_session):
        """Apply a discount to the order"""
        if not discount.available or not discount.group.available:
            return False
        
        # Calculate discount amount
        discount_amount = discount.calculate_discount_amount(self.subtotal)
        
        # Create order discount record
        order_discount = OrderDiscount(
            order_id=self.id,
            discount_id=discount.id,
            amount_applied=discount_amount,
            name=discount.name
        )
        
        # Add discount to order
        self.discounts.append(order_discount)
        
        # Recalculate total
        self.calculate_total(db_session)
        return True

    def get_square_amount(self):
        """Get amount to be charged via Square (in cents)"""
        if self.payment_method == PaymentMethod.CARD:
            return int(self.total * 100)  # Convert to cents
        return 0

    def to_dict(self):
        return {
            "order_id": self.id,
            "order_number": self.order_number,
            "status": self.status.value,
            "subtotal": float(self.subtotal),
            "discounts": [d.to_dict() for d in self.discounts],
            "total_discount": float(self.get_total_discount()),
            "tax": float(self.tax),
            "card_fee": float(self.card_fee),
            "total": float(self.total),
            "payment_method": self.payment_method.value if self.payment_method else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "ready_at": self.ready_at.isoformat() if self.ready_at else None,
            "done_at": self.done_at.isoformat() if self.done_at else None,
            "refunded_at": self.refunded_at.isoformat() if self.refunded_at else None,
            "items": [item.to_dict() for item in self.items],
            "prep_time": (self.ready_at - self.created_at).total_seconds() if self.ready_at and self.created_at else None,
            "ready_time": (self.done_at - self.ready_at).total_seconds() if self.done_at and self.ready_at else None,
            "total_time": (self.done_at - self.created_at).total_seconds() if self.done_at and self.created_at else None
        }

class OrderItem(Base):
    __tablename__ = 'order_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    item_price = Column(Float, nullable=False)  # Base price of item at time of order
    mods_price = Column(Float, default=0.00)    # Total price of all mods
    total_price = Column(Float, nullable=False)  # (item_price + mods_price) * quantity
    notes = Column(String)

    # Relationships
    order = relationship("Order", back_populates="items")
    item = relationship("Item", back_populates="order_items")
    mods = relationship("OrderItemMod", back_populates="order_item", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "item_id": self.item_id,
            "name": self.item.name,
            "quantity": self.quantity,
            "item_price": float(self.item_price),
            "mods_price": float(self.mods_price),
            "total_price": float(self.total_price),
            "notes": self.notes,
            "mods": [mod.to_dict() for mod in self.mods]
        }

class OrderItemMod(Base):
    __tablename__ = 'order_item_mods'

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_item_id = Column(Integer, ForeignKey('order_items.id'), nullable=False)
    mod_id = Column(Integer, ForeignKey('mods.id'), nullable=False)
    mod_price = Column(Float, nullable=False)  # Price of this mod at time of order
    mod_name = Column(String, nullable=False)  # Name of mod at time of order

    # Relationships
    order_item = relationship("OrderItem", back_populates="mods")
    mod = relationship("Mod", back_populates="order_item_mods")

    def to_dict(self):
        return {
            "mod_id": self.mod_id,
            "name": self.mod_name,
            "price": float(self.mod_price)
        }

class OrderHistory(Base):
    __tablename__ = 'order_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, nullable=False)
    order_number = Column(Integer, nullable=False)
    staff_id = Column(Integer, nullable=False)
    staff_name = Column(String, nullable=False)  # Store staff name at time of archiving
    status = Column(Enum(OrderStatus), nullable=False)
    
    # Price calculations at time of archiving
    subtotal = Column(Float, nullable=False)
    tax = Column(Float, nullable=False)
    card_fee = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    
    payment_method = Column(Enum(PaymentMethod))
    notes = Column(String)
    
    # Square payment details
    square_payment_id = Column(String)
    square_refund_id = Column(String)
    
    # Timing tracking
    created_at = Column(DateTime(timezone=True), nullable=False)
    ready_at = Column(DateTime(timezone=True))
    done_at = Column(DateTime(timezone=True))
    refunded_at = Column(DateTime(timezone=True))
    archived_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Store complete order data as JSON for historical reference
    items_data = Column(JSON, nullable=False)  # Store items and modifiers
    discounts_data = Column(JSON, nullable=False)  # Store discounts

    @classmethod
    def from_order(cls, order: Order) -> 'OrderHistory':
        """Create OrderHistory record from an Order"""
        return cls(
            order_id=order.id,
            order_number=order.order_number,
            staff_id=order.staff_id,
            staff_name=order.staff.name,
            status=order.status,
            subtotal=order.subtotal,
            tax=order.tax,
            card_fee=order.card_fee,
            total=order.total,
            payment_method=order.payment_method,
            notes=order.notes,
            square_payment_id=order.square_payment_id,
            square_refund_id=order.square_refund_id,
            created_at=order.created_at,
            ready_at=order.ready_at,
            done_at=order.done_at,
            refunded_at=order.refunded_at,
            items_data=[item.to_dict() for item in order.items],
            discounts_data=[discount.to_dict() for discount in order.discounts]
        )

    def to_dict(self):
        return {
            "order_id": self.order_id,
            "order_number": self.order_number,
            "staff_name": self.staff_name,
            "status": self.status.value,
            "subtotal": float(self.subtotal),
            "tax": float(self.tax),
            "card_fee": float(self.card_fee),
            "total": float(self.total),
            "payment_method": self.payment_method.value if self.payment_method else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "ready_at": self.ready_at.isoformat() if self.ready_at else None,
            "done_at": self.done_at.isoformat() if self.done_at else None,
            "refunded_at": self.refunded_at.isoformat() if self.refunded_at else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "items": self.items_data,
            "discounts": self.discounts_data
        } 