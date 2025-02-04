#!/usr/bin/env python3
import os
import sys
import json
import logging
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from models import (
    Base, Staff, Category, Item, ModList, Mod,
    DiscountGroup, CardFeeSettings, StaffShift,
    Order, OrderItem, OrderItemMod, OrderStatus, PaymentMethod
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_usb_mount():
    """Check if USB drive is mounted and create necessary directories"""
    usb_path = os.environ.get('USB_PATH', '/media/usbdrive')
    
    if not os.path.exists(usb_path):
        raise Exception(f"USB drive path {usb_path} does not exist")
    
    if not os.path.ismount(usb_path):
        raise Exception(f"No USB drive mounted at {usb_path}")
    
    db_dir = os.path.join(usb_path, 'pos_data')
    try:
        os.makedirs(db_dir, mode=0o755, exist_ok=True)
        logger.info(f"Created database directory at {db_dir}")
    except PermissionError as e:
        raise Exception(f"Permission denied creating database directory at {db_dir}: {e}")
    except OSError as e:
        raise Exception(f"Failed to create database directory at {db_dir}: {e}")
    
    return db_dir

def load_default_data():
    """Load default data from default_data.json"""
    default_data_path = Path(__file__).resolve().parent.parent / 'default_data.json'
    try:
        with open(default_data_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"default_data.json not found at {default_data_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing default_data.json: {e}")
        return None

def init_staff(session: Session, staff_data: list):
    """Initialize default staff"""
    if not session.query(Staff).first():
        for staff_member in staff_data:
            # Ensure staff ID is a six-digit number
            staff_id = 100000 + len(session.query(Staff).all())
            staff = Staff(
                id=staff_id,
                name=staff_member['name'],
                pin=staff_member['pin'],
                hourly_rate=staff_member['hourly_rate'],
                isAdmin=staff_member['isAdmin'],
                is_working=staff_member['working'],
                is_on_break=staff_member['break'],
                available=True
            )
            session.add(staff)
            logger.info(f"Added default staff member: {staff_member['name']}")

def init_categories(session: Session, categories_data: list):
    """Initialize default categories"""
    if not session.query(Category).first():
        for cat_data in categories_data:
            # Ensure category ID is a six-digit number
            category_id = cat_data.get('category_id')
            if not category_id or category_id < 100000 or category_id >= 1000000:
                category_id = 100000 + len(session.query(Category).all())
            
            category = Category(
                name=cat_data['name'],
                sort_order=cat_data['sort_order'],
                id=category_id,
                available=True
            )
            session.add(category)
            logger.info(f"Added category: {cat_data['name']}")

def init_items(session: Session, items_data: list):
    """Initialize default items"""
    if not session.query(Item).first():
        for item_data in items_data:
            # Ensure item ID is a six-digit number
            item_id = 100000 + len(session.query(Item).all())
            item = Item(
                id=item_id,
                name=item_data['name'],
                reg_price=item_data['reg_price'],
                event_price=item_data.get('event_price', item_data['reg_price']),
                category_id=item_data['category_id'],
                sort_order=item_data['sort_order'],
                available=item_data['available']
            )
            session.add(item)
            logger.info(f"Added item: {item_data['name']}")

def init_modlists(session: Session, modlists_data: list):
    """Initialize default modification lists"""
    if not session.query(ModList).first():
        for modlist_data in modlists_data:
            # Ensure modlist ID is a six-digit number
            modlist_id = 100000 + len(session.query(ModList).all())
            modlist = ModList(
                id=modlist_id,
                name=modlist_data['name'],
                min_selections=modlist_data['min_selections'],
                max_selections=modlist_data['max_selections'],
                sort_order=modlist_data.get('sort_order', 0),
                available=True
            )
            session.add(modlist)
            session.flush()
            
            for mod_data in modlist_data.get('mods', []):
                # Ensure mod ID is a six-digit number
                mod_id = 100000 + len(session.query(Mod).all())
                mod = Mod(
                    id=mod_id,
                    name=mod_data['name'],
                    mod_price=mod_data['mod_price'],
                    mod_list_id=modlist.id,
                    sort_order=mod_data.get('sort_order', 0),
                    available=True
                )
                session.add(mod)
            logger.info(f"Added modlist: {modlist_data['name']}")

def init_system_settings(session: Session):
    """Initialize system settings"""
    if not session.query(CardFeeSettings).first():
        card_settings = CardFeeSettings(
            enabled=True,
            fee_percentage=2.5,
            min_fee=0.50
        )
        session.add(card_settings)
        logger.info("Added default card fee settings")

def setup_database():
    """Main function to set up the database with all required tables and default data"""
    try:
        # Check USB mount and get database directory
        db_dir = check_usb_mount()
        db_path = os.path.join(db_dir, 'pos_db.sqlite')
        
        # Create database URL
        db_url = f"sqlite:///{db_path}"
        engine = create_engine(db_url)
        
        # Check if database is already initialized
        inspector = inspect(engine)
        if inspector.get_table_names():
            logger.info("Database already initialized, skipping setup")
            return True
        
        # Create all tables
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        
        # Load default data
        default_data = load_default_data()
        if not default_data:
            raise Exception("Failed to load default data")
        
        # Initialize data
        Session = sessionmaker(bind=engine)
        with Session() as session:
            init_staff(session, default_data['staff'])
            init_categories(session, default_data['categories'])
            init_items(session, default_data['items'])
            init_modlists(session, default_data['modlists'])
            init_system_settings(session)
            session.commit()
        
        logger.info("Database setup completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        return False

if __name__ == '__main__':
    if setup_database():
        sys.exit(0)
    else:
        sys.exit(1)