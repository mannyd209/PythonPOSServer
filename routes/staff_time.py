from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, constr
from typing import Optional
from datetime import datetime
from database import get_db
from models.staff import Staff, StaffShift

router = APIRouter(tags=["Staff Time"])

class PinAuth(BaseModel):
    pin: constr(min_length=4, max_length=4)

@router.post("/clock-in")
def clock_in(auth: PinAuth, db: Session = Depends(get_db)):
    """Clock in a staff member for their shift"""
    staff = db.query(Staff).filter(Staff.pin == auth.pin).first()
    if not staff:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    
    if not staff.available:
        raise HTTPException(status_code=403, detail="Staff member is not active")
        
    if staff.is_working:
        raise HTTPException(status_code=400, detail="Already clocked in")
    
    # Create new shift
    shift = StaffShift(
        staff_id=staff.id,
        clock_in=datetime.now(),
        hourly_rate=staff.hourly_rate
    )
    staff.is_working = True
    
    db.add(shift)
    db.commit()
    
    return {
        "success": True,
        "shift": shift.to_dict()
    }

@router.post("/clock-out")
def clock_out(auth: PinAuth, db: Session = Depends(get_db)):
    """Clock out a staff member from their shift"""
    staff = db.query(Staff).filter(Staff.pin == auth.pin).first()
    if not staff:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    
    if not staff.is_working:
        raise HTTPException(status_code=400, detail="Not clocked in")
        
    if staff.is_on_break:
        raise HTTPException(status_code=400, detail="Must end break before clocking out")
    
    # Find current shift
    shift = db.query(StaffShift)\
        .filter(StaffShift.staff_id == staff.id, StaffShift.clock_out == None)\
        .first()
    
    if not shift:
        raise HTTPException(status_code=404, detail="No active shift found")
    
    shift.clock_out = datetime.now()
    staff.is_working = False
    
    db.commit()
    
    return {
        "success": True,
        "shift": shift.to_dict()
    }

@router.post("/break/start")
def start_break(auth: PinAuth, db: Session = Depends(get_db)):
    """Start a break during the current shift"""
    staff = db.query(Staff).filter(Staff.pin == auth.pin).first()
    if not staff:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    
    if not staff.is_working:
        raise HTTPException(status_code=400, detail="Not clocked in")
        
    if staff.is_on_break:
        raise HTTPException(status_code=400, detail="Already on break")
    
    # Find current shift
    shift = db.query(StaffShift)\
        .filter(StaffShift.staff_id == staff.id, StaffShift.clock_out == None)\
        .first()
    
    if not shift:
        raise HTTPException(status_code=404, detail="No active shift found")
    
    shift.break_start = datetime.now()
    staff.is_on_break = True
    
    db.commit()
    
    return {
        "success": True,
        "shift": shift.to_dict()
    }

@router.post("/break/end")
def end_break(auth: PinAuth, db: Session = Depends(get_db)):
    """End a break during the current shift"""
    staff = db.query(Staff).filter(Staff.pin == auth.pin).first()
    if not staff:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    
    if not staff.is_working:
        raise HTTPException(status_code=400, detail="Not clocked in")
        
    if not staff.is_on_break:
        raise HTTPException(status_code=400, detail="Not on break")
    
    # Find current shift
    shift = db.query(StaffShift)\
        .filter(StaffShift.staff_id == staff.id, StaffShift.clock_out == None)\
        .first()
    
    if not shift:
        raise HTTPException(status_code=404, detail="No active shift found")
    
    shift.break_end = datetime.now()
    staff.is_on_break = False
    
    db.commit()
    
    return {
        "success": True,
        "shift": shift.to_dict()
    }

@router.get("/status")
def get_status(auth: PinAuth, db: Session = Depends(get_db)):
    """Get current working status and earnings for a staff member"""
    staff = db.query(Staff).filter(Staff.pin == auth.pin).first()
    if not staff:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    
    current_shift = None
    if staff.is_working:
        current_shift = db.query(StaffShift)\
            .filter(StaffShift.staff_id == staff.id, StaffShift.clock_out == None)\
            .first()
    
    return {
        "success": True,
        "staff": staff.to_dict(),
        "current_shift": current_shift.to_dict() if current_shift else None
    } 