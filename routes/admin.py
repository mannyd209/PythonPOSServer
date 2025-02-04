from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import Dict, Optional, List
from pydantic import BaseModel, Field, validator
import psutil
import os
import subprocess
from datetime import datetime
import shutil
from models import get_db, Staff, StaffRole, SystemSettings
from utils.auth import get_current_staff, verify_admin, verify_admin_token
import logging
from sqlalchemy.orm import Session
from models.system import CardFeeSettings
from utils.order_management import reset_order_numbers
import pytz

# Response Models
class SystemStats(BaseModel):
    """System statistics model"""
    cpu_temperature: float = Field(..., description="CPU temperature in Celsius")
    cpu_usage: float = Field(..., description="CPU usage percentage")
    memory_total: int = Field(..., description="Total memory in bytes")
    memory_used: int = Field(..., description="Used memory in bytes")
    memory_percent: float = Field(..., description="Memory usage percentage")
    disk_total: int = Field(..., description="Total disk space in bytes")
    disk_used: int = Field(..., description="Used disk space in bytes")
    disk_percent: float = Field(..., description="Disk usage percentage")
    uptime: int = Field(..., description="System uptime in seconds")
    timestamp: str = Field(..., description="Current UTC timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "cpu_temperature": 45.2,
                "cpu_usage": 25.6,
                "memory_total": 8589934592,
                "memory_used": 4294967296,
                "memory_percent": 50.0,
                "disk_total": 64424509440,
                "disk_used": 32212254720,
                "disk_percent": 50.0,
                "uptime": 86400,
                "timestamp": "2024-01-30T12:00:00Z"
            }
        }

class USBStatus(BaseModel):
    """USB drive status model"""
    is_mounted: bool = Field(..., description="Whether the USB drive is currently mounted")
    mount_options: str = Field(..., description="Current mount options if mounted")
    total_space: int = Field(..., description="Total space on USB drive in bytes")
    used_space: int = Field(..., description="Used space on USB drive in bytes")
    free_space: int = Field(..., description="Free space on USB drive in bytes")
    usage_percent: float = Field(..., description="USB drive usage percentage")
    device: str = Field(..., description="Device path of the USB drive")
    safe_to_remove: bool = Field(..., description="Whether it's safe to remove the USB drive")

    class Config:
        json_schema_extra = {
            "example": {
                "is_mounted": True,
                "mount_options": "rw,nosuid,nodev",
                "total_space": 64424509440,
                "used_space": 32212254720,
                "free_space": 32212254720,
                "usage_percent": 50.0,
                "device": "/dev/sda2",
                "safe_to_remove": False
            }
        }

class ServiceStatus(BaseModel):
    """Service status model"""
    status: str = Field(..., description="Current service status (active/inactive)")
    pid: int = Field(..., description="Process ID of the service")
    working_directory: str = Field(..., description="Current working directory")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "active",
                "pid": 1234,
                "working_directory": "/opt/pos"
            }
        }

class SystemStatus(BaseModel):
    """Complete system status model"""
    system: SystemStats = Field(..., description="System statistics")
    usb_drive: USBStatus = Field(..., description="USB drive status")
    pos_service: ServiceStatus = Field(..., description="POS service status")

class LogResponse(BaseModel):
    """Log response model"""
    service_logs: str = Field(..., description="Recent systemd service logs")
    application_logs: str = Field(..., description="Recent application logs")

    class Config:
        json_schema_extra = {
            "example": {
                "service_logs": "Jan 30 12:00:00 pos-backend[1234]: Started POS Backend Service",
                "application_logs": "2024-01-30 12:00:00 - INFO - Application started"
            }
        }

class StatusResponse(BaseModel):
    """Operation status response model"""
    status: str = Field(..., description="Operation status (success/error)")
    message: str = Field(..., description="Status message")
    usb_status: Optional[USBStatus] = Field(None, description="Current USB drive status")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Operation completed successfully",
                "usb_status": {
                    "is_mounted": True,
                    "mount_options": "rw,nosuid,nodev",
                    "total_space": 64424509440,
                    "used_space": 32212254720,
                    "free_space": 32212254720,
                    "usage_percent": 50.0,
                    "device": "/dev/sda2",
                    "safe_to_remove": False
                }
            }
        }

class SystemSettingsUpdate(BaseModel):
    timezone: str = Field(..., description="Timezone name (e.g., 'America/Los_Angeles')")
    order_number_format: str = Field(..., description="Order number format pattern")

    @validator('timezone')
    def validate_timezone(cls, v):
        try:
            pytz.timezone(v)
            return v
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValueError(f"Invalid timezone: {v}")

    class Config:
        json_schema_extra = {
            "example": {
                "timezone": "America/Los_Angeles",
                "order_number_format": "ORD-{number:04d}"
            }
        }

router = APIRouter(
    prefix="/admin",
    tags=["System Administration"],
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (Admin only)"},
        404: {"description": "Resource not found"},
        500: {"description": "Internal server error"}
    },
    dependencies=[Depends(verify_admin)]
)

logger = logging.getLogger(__name__)

# Helper function to check admin role
def check_admin_role(staff: Staff = Depends(get_current_staff)):
    """Check if staff member has admin role"""
    if staff.role != StaffRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    return staff

def get_system_status() -> Dict:
    """
    Get Raspberry Pi system status.
    
    Returns:
    - CPU temperature and usage
    - Memory statistics
    - Disk usage
    - System uptime
    - Current timestamp
    """
    try:
        cpu_temp = subprocess.check_output(['vcgencmd', 'measure_temp']).decode()
        temp = float(cpu_temp.replace('temp=', '').replace('\'C\n', ''))
    except:
        temp = 0.0

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    cpu_usage = psutil.cpu_percent(interval=1)
    
    return {
        "cpu_temperature": temp,
        "cpu_usage": cpu_usage,
        "memory_total": memory.total,
        "memory_used": memory.used,
        "memory_percent": memory.percent,
        "disk_total": disk.total,
        "disk_used": disk.used,
        "disk_percent": disk.percent,
        "uptime": int(psutil.boot_time()),
        "timestamp": datetime.utcnow().isoformat()
    }

def get_usb_status() -> Dict:
    """
    Get USB drive status.
    
    Returns:
    - Mount status and options
    - Space usage statistics
    - Device information
    - Safety status for removal
    """
    try:
        disk = psutil.disk_usage('/media/usbdrive')
        mounted = os.path.ismount('/media/usbdrive')
        
        if mounted:
            with open('/proc/mounts') as f:
                mount_info = [line for line in f if '/media/usbdrive' in line]
                mount_options = mount_info[0].split()[3] if mount_info else ''
        else:
            mount_options = ''
        
        return {
            "is_mounted": mounted,
            "mount_options": mount_options,
            "total_space": disk.total if mounted else 0,
            "used_space": disk.used if mounted else 0,
            "free_space": disk.free if mounted else 0,
            "usage_percent": disk.percent if mounted else 0,
            "device": "/dev/sda2",
            "safe_to_remove": not mounted
        }
    except Exception as e:
        logger.error(f"Error getting USB status: {e}")
        return {
            "is_mounted": False,
            "error": str(e),
            "safe_to_remove": True
        }

@router.get(
    "/status",
    response_model=SystemStatus,
    summary="Get System Status",
    response_description="Complete system status information",
    dependencies=[Depends(check_admin_role)]
)
async def system_status() -> Dict:
    """
    Get complete system status information.

    Retrieves comprehensive system information including:
    - CPU temperature and usage
    - Memory utilization
    - Disk space usage
    - System uptime
    - USB drive status
    - POS service status

    Returns:
    - system: System statistics
    - usb_drive: USB drive status
    - pos_service: Service status

    Raises:
    - 401: Not authenticated
    - 403: Not authorized (Admin only)
    """
    try:
        service_status = subprocess.check_output(
            ['systemctl', 'is-active', 'pos-backend.service']
        ).decode().strip()
    except:
        service_status = "unknown"

    return {
        "system": get_system_status(),
        "usb_drive": get_usb_status(),
        "pos_service": {
            "status": service_status,
            "pid": os.getpid(),
            "working_directory": os.getcwd()
        }
    }

@router.post(
    "/service/restart",
    response_model=StatusResponse,
    summary="Restart POS Service",
    response_description="Service restart status",
    dependencies=[Depends(check_admin_role)]
)
async def restart_service() -> Dict:
    """
    Restart the POS backend service.

    This operation will:
    1. Stop the current service
    2. Start a new service instance
    3. Return the operation status

    Note: This will cause a brief service interruption.

    Returns:
    - status: Operation status
    - message: Status message

    Raises:
    - 401: Not authenticated
    - 403: Not authorized (Admin only)
    - 500: Service restart failed
    """
    try:
        subprocess.run(['sudo', 'systemctl', 'restart', 'pos-backend.service'], check=True)
        return {"status": "success", "message": "Service restart initiated"}
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart service: {str(e)}"
        )

@router.post(
    "/system/restart",
    response_model=StatusResponse,
    summary="Restart System",
    response_description="System restart status",
    dependencies=[Depends(check_admin_role)]
)
async def restart_system() -> Dict:
    """
    Initiate a system restart.

    This operation will:
    1. Sync all filesystems
    2. Stop all services
    3. Restart the system

    Warning: This will interrupt all services until system restart completes.

    Returns:
    - status: Operation status
    - message: Status message

    Raises:
    - 401: Not authenticated
    - 403: Not authorized (Admin only)
    - 500: System restart failed
    """
    try:
        subprocess.run(['sudo', 'shutdown', '-r', '+0', '"Restart requested via Admin Dashboard"'], check=True)
        return {"status": "success", "message": "System restart initiated"}
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart system: {str(e)}"
        )

@router.post(
    "/usb/prepare-removal",
    response_model=StatusResponse,
    summary="Prepare USB Removal",
    response_description="USB drive preparation status",
    dependencies=[Depends(check_admin_role)]
)
async def prepare_usb_removal() -> Dict:
    """
    Prepare USB drive for safe removal.

    This operation will:
    1. Stop the POS service
    2. Sync all filesystems
    3. Unmount the USB drive
    4. Verify safe removal status

    Returns:
    - status: Operation status
    - message: Status message
    - usb_status: Current USB drive status

    Raises:
    - 401: Not authenticated
    - 403: Not authorized (Admin only)
    - 500: USB preparation failed
    """
    try:
        subprocess.run(['sudo', 'systemctl', 'stop', 'pos-backend.service'], check=True)
        subprocess.run(['sync'], check=True)
        subprocess.run(['sudo', 'umount', '/media/usbdrive'], check=True)
        
        return {
            "status": "success",
            "message": "USB drive is now safe to remove",
            "usb_status": get_usb_status()
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to prepare USB for removal: {str(e)}"
        )

@router.post(
    "/usb/remount",
    response_model=StatusResponse,
    summary="Remount USB Drive",
    response_description="USB drive remount status",
    dependencies=[Depends(check_admin_role)]
)
async def remount_usb() -> Dict:
    """
    Remount USB drive and restart services.

    This operation will:
    1. Mount the USB drive
    2. Wait for mount completion
    3. Start the POS service
    4. Verify mount status

    Returns:
    - status: Operation status
    - message: Status message
    - usb_status: Current USB drive status

    Raises:
    - 401: Not authenticated
    - 403: Not authorized (Admin only)
    - 500: USB remount failed
    """
    try:
        subprocess.run(['sudo', 'mount', '-a'], check=True)
        subprocess.run(['sleep', '2'], check=True)
        subprocess.run(['sudo', 'systemctl', 'start', 'pos-backend.service'], check=True)
        
        return {
            "status": "success",
            "message": "USB drive remounted and service started",
            "usb_status": get_usb_status()
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remount USB: {str(e)}"
        )

@router.get(
    "/logs",
    response_model=LogResponse,
    summary="Get System Logs",
    response_description="Recent system and application logs",
    dependencies=[Depends(check_admin_role)]
)
async def get_logs(
    lines: Optional[int] = Query(
        default=50,
        description="Number of log lines to return",
        ge=1,
        le=1000
    )
) -> LogResponse:
    """
    Get recent system and service logs.

    Retrieves the most recent logs from:
    - Systemd service logs
    - Application logs
    - System logs related to POS service

    Parameters:
    - lines: Number of recent log lines to retrieve (default: 50, max: 1000)

    Returns:
    - service_logs: Recent systemd service logs
    - application_logs: Recent application logs

    Raises:
    - 401: Not authenticated
    - 403: Not authorized (Admin only)
    - 500: Log retrieval failed
    """
    try:
        service_logs = subprocess.check_output(
            ['journalctl', '-u', 'pos-backend.service', '-n', str(lines)],
            universal_newlines=True
        )
        
        app_log_path = "logs/pos_backend.log"
        if os.path.exists(app_log_path):
            with open(app_log_path, 'r') as f:
                app_logs = ''.join(f.readlines()[-lines:])
        else:
            app_logs = "No application logs found"
        
        return LogResponse(
            service_logs=service_logs,
            application_logs=app_logs
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve logs: {str(e)}")

class CardFeeSettingsUpdate(BaseModel):
    available: Optional[bool] = Field(None, description="Whether to apply card fees")
    percentage_amount: Optional[float] = Field(None, ge=0, le=1, description="Card fee percentage (0-1)")
    min_fee: Optional[float] = Field(None, ge=0, description="Minimum card fee amount")

    class Config:
        json_schema_extra = {
            "example": {
                "available": True,
                "percentage_amount": 0.05,
                "min_fee": 0.30
            }
        }

@router.get(
    "/card-fee",
    response_model=dict,
    summary="Get Card Fee Settings",
    response_description="Current card fee settings"
)
async def get_card_fee_settings(db: Session = Depends(get_db)):
    """Get current card fee settings"""
    settings = db.query(CardFeeSettings).first()
    if not settings:
        # Create default settings if none exist
        settings = CardFeeSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return settings.to_dict()

@router.patch(
    "/card-fee",
    response_model=dict,
    summary="Update Card Fee Settings",
    response_description="Updated card fee settings"
)
async def update_card_fee_settings(
    updates: CardFeeSettingsUpdate,
    db: Session = Depends(get_db)
):
    """Update card fee settings"""
    settings = db.query(CardFeeSettings).first()
    if not settings:
        settings = CardFeeSettings()
        db.add(settings)
    
    # Update only provided fields
    if updates.available is not None:
        settings.available = updates.available
    if updates.percentage_amount is not None:
        settings.percentage_amount = updates.percentage_amount
    if updates.min_fee is not None:
        settings.min_fee = updates.min_fee
    
    db.commit()
    db.refresh(settings)
    
    return settings.to_dict()

@router.post("/reset-order-numbers")
def reset_orders(db: Session = Depends(get_db), _=Depends(verify_admin_token)):
    """
    Manually reset order numbers.
    Requires admin authentication.
    """
    success = reset_order_numbers(db)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to reset order numbers")
    return {"message": "Order numbers reset successfully"}

@router.get("/system/timezone", response_model=dict)
async def get_system_timezone(db: Session = Depends(get_db)):
    """Get current system timezone setting"""
    settings = db.query(SystemSettings).first()
    if not settings:
        settings = SystemSettings()
        db.add(settings)
        db.commit()
    
    return {"timezone": settings.timezone}

@router.patch("/system/timezone")
async def update_system_timezone(
    updates: SystemSettingsUpdate,
    db: Session = Depends(get_db),
    _=Depends(verify_admin_token)
):
    """Update system timezone (Admin only)"""
    try:
        settings = db.query(SystemSettings).first()
        if not settings:
            settings = SystemSettings()
            db.add(settings)
        
        settings.timezone = updates.timezone
        db.commit()
        
        return {"message": f"Timezone updated to {updates.timezone}"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update timezone: {str(e)}"
        )

@router.get(
    "/settings",
    response_model=dict,
    summary="Get System Settings",
    response_description="Current system settings"
)
async def get_settings(db: Session = Depends(get_db)):
    """Get current system settings"""
    settings = db.query(SystemSettings).first()
    if not settings:
        settings = SystemSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return settings.to_dict()

@router.patch(
    "/settings",
    response_model=dict,
    summary="Update System Settings",
    response_description="Updated system settings"
)
async def update_settings(
    updates: SystemSettingsUpdate,
    db: Session = Depends(get_db)
):
    """Update system settings"""
    settings = db.query(SystemSettings).first()
    if not settings:
        settings = SystemSettings()
        db.add(settings)
    
    settings.timezone = updates.timezone
    settings.order_number_format = updates.order_number_format
    
    db.commit()
    db.refresh(settings)
    
    return settings.to_dict()

@router.get(
    "/health",
    response_model=dict,
    summary="System Health Check",
    response_description="Current system health status"
)
async def health_check(db: Session = Depends(get_db)):
    """Check system health status"""
    try:
        # Check database connection
        db_status = "connected"
        db.execute("SELECT 1")
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
        "websocket": {
            "active_connections": 0  # Replace with actual WebSocket manager stats
        }
    } 