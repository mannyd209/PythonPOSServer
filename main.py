from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, time, timedelta
from database import SessionLocal
from utils.order_management import daily_order_cleanup
from models import Order, SystemSettings
from sqlalchemy import func
import pytz
import logging

logger = logging.getLogger(__name__)

# ... existing imports and app setup ...

# Initialize scheduler
scheduler = BackgroundScheduler()

def get_system_timezone(db: Session = None) -> str:
    """Get system timezone from settings or return default"""
    try:
        if db is None:
            db = SessionLocal()
        settings = db.query(SystemSettings).first()
        return settings.timezone if settings else 'America/Los_Angeles'
    except Exception as e:
        logger.error(f"Failed to get system timezone: {e}")
        return 'America/Los_Angeles'
    finally:
        if db is not None:
            db.close()

def get_local_time(db: Session = None):
    """Get current time in system timezone"""
    try:
        timezone = get_system_timezone(db)
        local_tz = pytz.timezone(timezone)
        return datetime.now(local_tz)
    except Exception as e:
        logger.error(f"Failed to get local time: {e}")
        # Fall back to UTC if timezone conversion fails
        return datetime.now(pytz.UTC)

def run_daily_cleanup():
    """
    Run the daily cleanup task with a new database session
    """
    db = SessionLocal()
    try:
        logger.info("Starting scheduled daily cleanup at 3 AM system time")
        success = daily_order_cleanup(db)
        if success:
            # Update last reset time in database
            settings = db.query(SystemSettings).first()
            if not settings:
                settings = SystemSettings()
                db.add(settings)
            settings.last_order_reset = get_local_time(db)
            db.commit()
            logger.info("Daily cleanup completed successfully")
        else:
            logger.error("Daily cleanup failed")
    except Exception as e:
        logger.error(f"Error in daily cleanup: {e}")
        db.rollback()
    finally:
        db.close()

def check_and_run_cleanup():
    """
    Check if cleanup should run on startup based on last reset time
    and current time
    """
    db = SessionLocal()
    try:
        current_time = get_local_time(db)
        logger.info(f"Checking if cleanup needed at startup. Current time: {current_time}")
        
        # Get last reset time from database
        settings = db.query(SystemSettings).first()
        if not settings or not settings.last_order_reset:
            logger.info("No previous reset time found, running cleanup")
            run_daily_cleanup()
            return
        
        # Convert stored UTC time to system timezone
        timezone = get_system_timezone(db)
        last_db_reset = settings.last_order_reset.astimezone(pytz.timezone(timezone))
        
        # Calculate when the last 3 AM should have been
        last_three_am = current_time.replace(hour=3, minute=0, second=0, microsecond=0)
        if current_time.hour < 3:
            last_three_am = last_three_am - timedelta(days=1)
        
        # If last reset was before the last 3 AM, we need to run cleanup
        if last_db_reset < last_three_am:
            logger.info(f"Last reset ({last_db_reset}) was before last 3 AM ({last_three_am}), running cleanup")
            run_daily_cleanup()
        else:
            logger.info("No cleanup needed at startup")
            
    except Exception as e:
        logger.error(f"Error checking cleanup status: {e}")
    finally:
        db.close()

# Schedule daily cleanup at 3 AM system timezone
try:
    db = SessionLocal()
    timezone = get_system_timezone(db)
    scheduler.add_job(
        run_daily_cleanup,
        'cron',
        hour=3,
        minute=0,
        timezone=pytz.timezone(timezone)
    )
    logger.info(f"Scheduled daily cleanup for 3 AM {timezone}")
except Exception as e:
    logger.error(f"Failed to schedule cleanup job: {e}")
finally:
    db.close()

@app.on_event("startup")
async def startup_event():
    try:
        # Check if cleanup needed on startup
        check_and_run_cleanup()
        # Start the scheduler
        scheduler.start()
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    try:
        scheduler.shutdown()
        logger.info("Scheduler shut down successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# ... rest of the FastAPI app setup ... 