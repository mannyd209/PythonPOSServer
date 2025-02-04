from typing import Dict, Set
from fastapi import WebSocket
import json
import logging
import asyncio
from enum import Enum

logger = logging.getLogger(__name__)

class ClientType(str, Enum):
    POS = "pos"
    CUSTOMER_DISPLAY = "customer_display"
    KITCHEN_DISPLAY = "kitchen_display"

class ConnectionManager:
    def __init__(self):
        # Store connections by type and ID
        self.connections: Dict[ClientType, Dict[str, WebSocket]] = {
            ClientType.POS: {},
            ClientType.CUSTOMER_DISPLAY: {},
            ClientType.KITCHEN_DISPLAY: {}
        }
        
        # Store active orders being viewed by each display
        self.active_orders: Dict[str, Set[int]] = {}
    
    async def connect(self, websocket: WebSocket, client_type: ClientType, client_id: str):
        """Connect a new client"""
        await websocket.accept()
        self.connections[client_type][client_id] = websocket
        self.active_orders[client_id] = set()
        logger.info(f"New {client_type} connection: {client_id}")
    
    def disconnect(self, client_type: ClientType, client_id: str):
        """Disconnect a client"""
        if client_id in self.connections[client_type]:
            del self.connections[client_type][client_id]
        if client_id in self.active_orders:
            del self.active_orders[client_id]
        logger.info(f"{client_type} disconnected: {client_id}")
    
    def add_active_order(self, client_id: str, order_id: int):
        """Add an order to a client's active orders"""
        if client_id in self.active_orders:
            self.active_orders[client_id].add(order_id)
    
    def remove_active_order(self, client_id: str, order_id: int):
        """Remove an order from a client's active orders"""
        if client_id in self.active_orders:
            self.active_orders[client_id].discard(order_id)
    
    async def broadcast_to_type(self, client_type: ClientType, message: dict):
        """Broadcast message to all clients of a specific type"""
        disconnected = []
        for client_id, connection in self.connections[client_type].items():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to {client_type} {client_id}: {e}")
                disconnected.append((client_type, client_id))
        
        # Clean up disconnected clients
        for client_type, client_id in disconnected:
            self.disconnect(client_type, client_id)
    
    async def send_to_client(self, client_type: ClientType, client_id: str, message: dict):
        """Send message to a specific client"""
        if client_id in self.connections[client_type]:
            try:
                await self.connections[client_type][client_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending to {client_type} {client_id}: {e}")
                self.disconnect(client_type, client_id)
    
    async def broadcast_order_update(self, order_data: dict):
        """Broadcast order updates to relevant clients"""
        order_id = order_data["id"]
        
        # Send to all POS clients
        await self.broadcast_to_type(ClientType.POS, {
            "type": "order_update",
            "data": order_data
        })
        
        # Send to customer displays viewing this order
        for client_id, orders in self.active_orders.items():
            if order_id in orders:
                await self.send_to_client(
                    ClientType.CUSTOMER_DISPLAY,
                    client_id,
                    {
                        "type": "order_update",
                        "data": order_data
                    }
                )
        
        # Send to kitchen displays if order is open
        if order_data.get("status") == "open":
            await self.broadcast_to_type(ClientType.KITCHEN_DISPLAY, {
                "type": "order_update",
                "data": order_data
            })
    
    async def broadcast_payment_update(self, payment_data: dict):
        """Broadcast payment status updates"""
        order_id = payment_data.get("order_id")
        
        # Send to POS clients
        await self.broadcast_to_type(ClientType.POS, {
            "type": "payment_update",
            "data": payment_data
        })
        
        # Send to customer displays viewing this order
        if order_id:
            for client_id, orders in self.active_orders.items():
                if order_id in orders:
                    await self.send_to_client(
                        ClientType.CUSTOMER_DISPLAY,
                        client_id,
                        {
                            "type": "payment_update",
                            "data": payment_data
                        }
                    )
    
    async def broadcast_catalog_update(self, update_data: dict):
        """Broadcast catalog updates (items, categories, etc.)"""
        # Send to all POS and customer display clients
        message = {
            "type": "catalog_update",
            "data": update_data
        }
        await self.broadcast_to_type(ClientType.POS, message)
        await self.broadcast_to_type(ClientType.CUSTOMER_DISPLAY, message)

# Create global connection manager instance
manager = ConnectionManager() 