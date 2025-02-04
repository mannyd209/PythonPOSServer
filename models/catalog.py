from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Table, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from .base import Base

# Many-to-many relationship between items and mod lists
# This table allows items to have multiple modifier lists (e.g., a burger can have both
# "toppings" and "cheese options" modifier lists)
item_modlist = Table(
    'item_modlist',
    Base.metadata,
    Column('item_id', Integer, ForeignKey('items.id')),
    Column('modlist_id', Integer, ForeignKey('mod_lists.id'))
)

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    sort_order = Column(Integer, default=0)
    available = Column(Boolean, default=True)

    # Validation for six-digit ID
    __table_args__ = (
        CheckConstraint('id >= 100000 AND id < 1000000', name='check_six_digit_id'),
        {'sqlite_autoincrement': True}  # Ensure SQLite uses true autoincrement
    )

    # Relationships
    items = relationship("Item", back_populates="category")

    def to_dict(self):
        return {
            "name": self.name,
            "sort_order": self.sort_order,
            "category_id": self.id,
            "available": self.available
        }

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    reg_price = Column(Float, nullable=False)
    event_price = Column(Float, nullable=False)
    sort_order = Column(Integer, default=0)
    available = Column(Boolean, default=True)

    # Validation for six-digit ID
    __table_args__ = (
        CheckConstraint('id >= 100000 AND id < 1000000', name='check_item_six_digit_id'),
        {'sqlite_autoincrement': True}  # Ensure SQLite uses true autoincrement
    )

    # Relationships
    category = relationship("Category", back_populates="items")
    mod_lists = relationship("ModList", secondary=item_modlist, back_populates="items")
    order_items = relationship("OrderItem", back_populates="item")

    def to_dict(self):
        return {
            "name": self.name,
            "item_id": self.id,
            "category_id": self.category_id,
            "reg_price": float(self.reg_price),
            "event_price": float(self.event_price),
            "sort_order": self.sort_order,
            "available": self.available,
            "mod_lists": [ml.to_dict() for ml in self.mod_lists]
        }

class ModList(Base):
    __tablename__ = "mod_lists"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    min_selections = Column(Integer, default=0)
    max_selections = Column(Integer)
    sort_order = Column(Integer, default=0)
    available = Column(Boolean, default=True)

    # Validation for six-digit ID
    __table_args__ = (
        CheckConstraint('id >= 100000 AND id < 1000000', name='check_modlist_six_digit_id'),
        {'sqlite_autoincrement': True}  # Ensure SQLite uses true autoincrement
    )

    # Relationships
    items = relationship("Item", secondary=item_modlist, back_populates="mod_lists")
    mods = relationship("Mod", back_populates="mod_list", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "name": self.name,
            "mod_list_id": self.id,
            "min_selections": self.min_selections,
            "max_selections": self.max_selections,
            "sort_order": self.sort_order,
            "available": self.available,
            "mods": [mod.to_dict() for mod in self.mods]
        }

class Mod(Base):
    __tablename__ = "mods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mod_list_id = Column(Integer, ForeignKey("mod_lists.id"), nullable=False)
    name = Column(String, nullable=False)

    # Validation for six-digit ID
    __table_args__ = (
        CheckConstraint('id >= 100000 AND id < 1000000', name='check_mod_six_digit_id'),
        {'sqlite_autoincrement': True}  # Ensure SQLite uses true autoincrement
    )
    mod_price = Column(Float, default=0.00)
    sort_order = Column(Integer, default=0)
    available = Column(Boolean, default=True)

    # Relationships
    mod_list = relationship("ModList", back_populates="mods")
    order_item_mods = relationship("OrderItemMod", back_populates="mod")

    def to_dict(self):
        return {
            "name": self.name,
            "mod_price": float(self.mod_price),
            "sort_order": self.sort_order,
            "available": self.available
        }