from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.sql import func
from .base import Base

class CardFeeSettings(Base):
    __tablename__ = 'card_fee_settings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    available = Column(Boolean, default=True)
    percentage_amount = Column(Float, default=0.05)  # 5% default
    min_fee = Column(Float, default=0.30)  # 30 cents minimum
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "available": self.available,
            "percentage_amount": float(self.percentage_amount),
            "min_fee": float(self.min_fee),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class SystemSettings(Base):
    __tablename__ = 'system_settings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    last_order_reset = Column(DateTime(timezone=True))
    timezone = Column(String, default='America/Los_Angeles')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def to_dict(self):
        return {
            "last_order_reset": self.last_order_reset.isoformat() if self.last_order_reset else None,
            "timezone": self.timezone,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        } 