from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPBasic, HTTPBasicCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from models import Staff, get_db
from config import SECRET_KEY

# Constants
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
security = HTTPBasic()

def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    """Verify a PIN against its hash"""
    return pwd_context.verify(plain_pin, hashed_pin)

def get_pin_hash(pin: str) -> str:
    """Get hash of a PIN"""
    return pwd_context.hash(pin)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_staff(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Authenticate staff member using 4-digit PIN
    The PIN is passed as the username, password field is ignored
    """
    try:
        pin = credentials.username
        if not pin.isdigit() or len(pin) != 4:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid PIN format. Must be 4 digits.",
                headers={"WWW-Authenticate": "Basic"},
            )
        
        staff = db.query(Staff).filter(Staff.pin == pin).first()
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid PIN",
                headers={"WWW-Authenticate": "Basic"},
            )
        
        return staff
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

async def verify_admin(staff: Staff = Depends(get_current_staff)):
    """Verify staff member has admin privileges"""
    if not staff.isAdmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return staff

def authenticate_staff(pin: str, db: Session) -> Optional[Staff]:
    """Authenticate a staff member by PIN"""
    staff = db.query(Staff).filter(Staff.active == True).all()
    
    # Check each staff member's PIN
    for s in staff:
        if verify_pin(pin, s.pin):
            return s
    
    return None