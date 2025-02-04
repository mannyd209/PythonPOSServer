from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field, constr, validator

from models import Staff, StaffShift, StaffRole, get_db
from utils.auth import (
    authenticate_staff,
    create_access_token,
    get_current_staff,
    get_pin_hash
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
    responses={
        401: {"description": "Authentication failed"},
        403: {"description": "Permission denied"},
    }
)

# Pydantic models for request/response
class Token(BaseModel):
    """JWT token response model"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(..., description="Token type (bearer)")
    staff: dict = Field(..., description="Staff member details")

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1...",
                "token_type": "bearer",
                "staff": {
                    "id": 1,
                    "name": "John Doe",
                    "role": "STAFF",
                    "active": True
                }
            }
        }

class PinLogin(BaseModel):
    """PIN login request model"""
    pin: str = Field(..., min_length=4, max_length=8, description="Staff PIN code")
    device_id: str = Field(..., description="Unique device identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "pin": "1234",
                "device_id": "iPad-POS-1"
            }
        }

class StaffCreate(BaseModel):
    """Staff creation request model"""
    name: str = Field(..., min_length=2, description="Staff member's name")
    pin: str = Field(..., min_length=4, max_length=8, description="PIN code for login")
    hourly_rate: float = Field(..., gt=0, description="Hourly pay rate")
    role: StaffRole = Field(..., description="Staff role (ADMIN, MANAGER, STAFF)")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "pin": "1234",
                "hourly_rate": 15.50,
                "role": "STAFF"
            }
        }

class StaffUpdate(BaseModel):
    """Staff update request model"""
    name: str | None = Field(None, min_length=2, description="Staff member's name")
    pin: str | None = Field(None, min_length=4, max_length=8, description="PIN code for login")
    hourly_rate: float | None = Field(None, gt=0, description="Hourly pay rate")
    role: StaffRole | None = Field(None, description="Staff role (ADMIN, MANAGER, STAFF)")
    active: bool | None = Field(None, description="Staff active status")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "hourly_rate": 16.50,
                "role": "MANAGER",
                "active": True
            }
        }

class LoginRequest(BaseModel):
    pin: constr(min_length=4, max_length=4)  # 4-digit PIN

    @validator('pin')
    def validate_pin(cls, v):
        if not v.isdigit():
            raise ValueError('PIN must contain only digits')
        return v

@router.post("/login")
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    Login with a 4-digit PIN.
    Returns staff information and permissions if successful.
    """
    staff = db.query(Staff).filter(Staff.pin == login_data.pin).first()
    
    if not staff:
        raise HTTPException(status_code=401, detail="Invalid PIN")
        
    if not staff.available:
        raise HTTPException(status_code=403, detail="Staff member is not active")
    
    return {
        "success": True,
        "staff": staff.to_dict()
    }

@router.post("/verify-admin")
def verify_admin(login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    Verify if a PIN belongs to an admin staff member.
    Returns admin status if successful.
    """
    staff = db.query(Staff).filter(Staff.pin == login_data.pin).first()
    
    if not staff:
        raise HTTPException(status_code=401, detail="Invalid PIN")
        
    if not staff.available:
        raise HTTPException(status_code=403, detail="Staff member is not active")
        
    if not staff.isAdmin:
        raise HTTPException(status_code=403, detail="Staff member is not an admin")
    
    return {
        "success": True,
        "staff": staff.to_dict()
    }

@router.post("/clock-in", response_model=dict, status_code=status.HTTP_201_CREATED)
async def clock_in(
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """
    Clock in a staff member for a new shift.

    Requires authentication.
    Creates a new shift record with clock-in time.

    Returns:
    - Shift details including clock-in time

    Raises:
    - 400: Already clocked in
    - 401: Not authenticated
    """
    active_shift = db.query(StaffShift).filter(
        StaffShift.staff_id == current_staff.id,
        StaffShift.clock_out == None
    ).first()
    
    if active_shift:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already clocked in"
        )
    
    shift = StaffShift(staff_id=current_staff.id)
    db.add(shift)
    db.commit()
    db.refresh(shift)
    
    return shift.to_dict()

@router.post("/clock-out", response_model=dict)
async def clock_out(
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """
    Clock out the current staff member.

    Requires authentication.
    Ends the current active shift.

    Returns:
    - Complete shift details including duration

    Raises:
    - 400: Not clocked in
    - 401: Not authenticated
    """
    active_shift = db.query(StaffShift).filter(
        StaffShift.staff_id == current_staff.id,
        StaffShift.clock_out == None
    ).first()
    
    if not active_shift:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not clocked in"
        )
    
    active_shift.clock_out = datetime.utcnow()
    db.commit()
    db.refresh(active_shift)
    
    return active_shift.to_dict()

@router.post("/break-start", response_model=dict)
async def start_break(
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """
    Start a break during the current shift.

    Requires authentication.
    Records break start time for the current shift.

    Returns:
    - Updated shift details

    Raises:
    - 400: Not clocked in or already on break
    - 401: Not authenticated
    """
    active_shift = db.query(StaffShift).filter(
        StaffShift.staff_id == current_staff.id,
        StaffShift.clock_out == None
    ).first()
    
    if not active_shift:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not clocked in"
        )
    
    if active_shift.break_start and not active_shift.break_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already on break"
        )
    
    active_shift.break_start = datetime.utcnow()
    db.commit()
    db.refresh(active_shift)
    
    return active_shift.to_dict()

@router.post("/break-end", response_model=dict)
async def end_break(
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """
    End the current break.

    Requires authentication.
    Records break end time for the current shift.

    Returns:
    - Updated shift details including break duration

    Raises:
    - 400: Not on break or break already ended
    - 401: Not authenticated
    """
    active_shift = db.query(StaffShift).filter(
        StaffShift.staff_id == current_staff.id,
        StaffShift.clock_out == None
    ).first()
    
    if not active_shift or not active_shift.break_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not on break"
        )
    
    if active_shift.break_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Break already ended"
        )
    
    active_shift.break_end = datetime.utcnow()
    db.commit()
    db.refresh(active_shift)
    
    return active_shift.to_dict()

@router.post("/staff", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_staff(
    staff_data: StaffCreate,
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """
    Create a new staff member.

    Requires manager or admin role.
    Creates a new staff record with the provided details.

    Parameters:
    - name: Staff member's name
    - pin: Login PIN code
    - hourly_rate: Pay rate
    - role: Staff role (ADMIN, MANAGER, STAFF)

    Returns:
    - Created staff member details

    Raises:
    - 401: Not authenticated
    - 403: Not authorized (requires manager/admin)
    """
    if current_staff.role not in [StaffRole.MANAGER, StaffRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create staff"
        )
    
    new_staff = Staff(
        name=staff_data.name,
        pin=get_pin_hash(staff_data.pin),
        hourly_rate=staff_data.hourly_rate,
        role=staff_data.role
    )
    
    db.add(new_staff)
    db.commit()
    db.refresh(new_staff)
    
    return new_staff.to_dict()

@router.get("/staff", response_model=List[dict])
async def list_staff(
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """
    List all staff members.

    Requires manager or admin role.
    Returns a list of all staff members and their details.

    Returns:
    - List of staff members

    Raises:
    - 401: Not authenticated
    - 403: Not authorized (requires manager/admin)
    """
    if current_staff.role not in [StaffRole.MANAGER, StaffRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view staff list"
        )
    
    staff = db.query(Staff).all()
    return [s.to_dict() for s in staff]

@router.put("/staff/{staff_id}", response_model=dict)
async def update_staff(
    staff_id: int,
    staff_data: StaffUpdate,
    current_staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    """
    Update a staff member's details.

    Requires manager or admin role.
    Updates specified fields for the given staff member.

    Parameters:
    - staff_id: ID of staff member to update
    - name: New name (optional)
    - pin: New PIN code (optional)
    - hourly_rate: New pay rate (optional)
    - role: New role (optional)
    - active: New active status (optional)

    Returns:
    - Updated staff member details

    Raises:
    - 401: Not authenticated
    - 403: Not authorized (requires manager/admin)
    - 404: Staff member not found
    """
    if current_staff.role not in [StaffRole.MANAGER, StaffRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update staff"
        )
    
    staff = db.query(Staff).filter(Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )
    
    # Update fields if provided
    if staff_data.name is not None:
        staff.name = staff_data.name
    if staff_data.pin is not None:
        staff.pin = get_pin_hash(staff_data.pin)
    if staff_data.hourly_rate is not None:
        staff.hourly_rate = staff_data.hourly_rate
    if staff_data.role is not None:
        staff.role = staff_data.role
    if staff_data.active is not None:
        staff.active = staff_data.active
    
    db.commit()
    db.refresh(staff)
    
    return staff.to_dict()