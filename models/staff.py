from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Staff(Base):
    __tablename__ = 'staff'

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String, nullable=False)
    pin = Column(String(4), nullable=False, unique=True)  # 4-digit PIN
    hourly_rate = Column(Float, default=0.00)
    isAdmin = Column(Boolean, default=False)
    is_working = Column(Boolean, default=False)
    is_on_break = Column(Boolean, default=False)
    available = Column(Boolean, default=True)

    # Validation for six-digit ID
    __table_args__ = (
        CheckConstraint('id >= 100000 AND id < 1000000', name='check_staff_six_digit_id'),
        {'sqlite_autoincrement': True}  # Ensure SQLite uses true autoincrement
    )

    # Relationships
    shifts = relationship("StaffShift", back_populates="staff")
    orders = relationship("Order", back_populates="staff")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "isAdmin": self.isAdmin,
            "working": self.is_working,
            "break": self.is_on_break,
            "available": self.available
        }

class StaffShift(Base):
    __tablename__ = 'staff_shifts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    staff_id = Column(Integer, ForeignKey('staff.id'), nullable=False)
    clock_in = Column(DateTime(timezone=True), nullable=False)

    # Validation for six-digit ID
    __table_args__ = (
        CheckConstraint('id >= 100000 AND id < 1000000', name='check_staffshift_six_digit_id'),
        {'sqlite_autoincrement': True}  # Ensure SQLite uses true autoincrement
    )
    clock_out = Column(DateTime(timezone=True))
    break_start = Column(DateTime(timezone=True))
    break_end = Column(DateTime(timezone=True))
    hourly_rate = Column(Float, nullable=False)  # Rate for this shift
    
    # Relationships
    staff = relationship("Staff", back_populates="shifts")

    def calculate_earnings(self):
        """Calculate earnings for this shift"""
        if not self.clock_in:
            return 0.0
        
        end_time = self.clock_out or datetime.now()
        total_hours = (end_time - self.clock_in).total_seconds() / 3600
        
        if self.break_start and self.break_end:
            break_hours = (self.break_end - self.break_start).total_seconds() / 3600
            total_hours -= break_hours
        elif self.break_start:  # Break started but not ended
            break_hours = (datetime.now() - self.break_start).total_seconds() / 3600
            total_hours -= break_hours
            
        return round(total_hours * self.hourly_rate, 2)

    def calculate_break_hours(self):
        """Calculate total break hours"""
        if not self.break_start:
            return 0.0
        
        break_end = self.break_end or datetime.now()
        return round((break_end - self.break_start).total_seconds() / 3600, 2)

    def calculate_hours_worked(self):
        """Calculate total hours worked (excluding breaks)"""
        if not self.clock_in:
            return 0.0
        
        end_time = self.clock_out or datetime.now()
        total_hours = (end_time - self.clock_in).total_seconds() / 3600
        
        # Subtract break time
        total_hours -= self.calculate_break_hours()
        
        return round(total_hours, 2)

    def to_dict(self):
        return {
            "shift_id": self.id,
            "clock_in": self.clock_in.isoformat() if self.clock_in else None,
            "clock_out": self.clock_out.isoformat() if self.clock_out else None,
            "break_start": self.break_start.isoformat() if self.break_start else None,
            "break_end": self.break_end.isoformat() if self.break_end else None,
            "current_earnings": self.calculate_earnings(),
            "hours_worked": self.calculate_hours_worked(),
            "break_hours": self.calculate_break_hours()
        }
