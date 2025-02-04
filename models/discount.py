from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from .base import Base

class DiscountGroup(Base):
    __tablename__ = 'discount_groups'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, default="Discounts")
    discount_group_id = Column(Integer, nullable=False, default=999999)
    available = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)

    # Validation for six-digit ID
    __table_args__ = (
        CheckConstraint('id >= 100000 AND id < 1000000', name='check_discountgroup_six_digit_id'),
        {'sqlite_autoincrement': True}  # Ensure SQLite uses true autoincrement
    )

    # Relationships
    discounts = relationship("Discount", back_populates="group", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "name": self.name,
            "discount_group_id": self.discount_group_id,
            "available": self.available,
            "sort_order": self.sort_order,
            "discounts": [d.to_dict() for d in self.discounts]
        }

class Discount(Base):
    __tablename__ = 'discounts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey('discount_groups.id'), nullable=False)
    name = Column(String, nullable=False)

    # Validation for six-digit ID
    __table_args__ = (
        CheckConstraint('id >= 100000 AND id < 1000000', name='check_discount_six_digit_id'),
        {'sqlite_autoincrement': True}  # Ensure SQLite uses true autoincrement
    )
    amount = Column(Float, nullable=False)  # Positive for percentage, negative for flat amount
    is_percentage = Column(Boolean, default=True)
    sort_order = Column(Integer, nullable=False)
    available = Column(Boolean, default=True)

    # Relationships
    group = relationship("DiscountGroup", back_populates="discounts")
    order_discounts = relationship("OrderDiscount", back_populates="discount")

    def to_dict(self):
        return {
            "name": self.name,
            "amount": float(self.amount),
            "isPercentage": self.is_percentage,
            "sort_order": self.sort_order,
            "available": self.available
        }

    def calculate_discount_amount(self, subtotal: float) -> float:
        """Calculate the discount amount based on the subtotal"""
        if not self.available or not self.group.available:
            return 0.0
        
        if self.is_percentage:
            return round((subtotal * self.amount / 100), 2)
        return abs(self.amount)  # Return positive amount for flat discounts

class OrderDiscount(Base):
    __tablename__ = 'order_discounts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    discount_id = Column(Integer, ForeignKey('discounts.id'), nullable=False)

    # Validation for six-digit ID
    __table_args__ = (
        CheckConstraint('id >= 100000 AND id < 1000000', name='check_orderdiscount_six_digit_id'),
        {'sqlite_autoincrement': True}  # Ensure SQLite uses true autoincrement
    )
    amount_applied = Column(Float, nullable=False)  # Actual amount applied to the order
    name = Column(String, nullable=False)  # Store name at time of order

    # Relationships
    order = relationship("Order", back_populates="discounts")
    discount = relationship("Discount", back_populates="order_discounts")

    def to_dict(self):
        return {
            "discount_id": self.discount_id,
            "name": self.name,
            "amount_applied": float(self.amount_applied)
        }