from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from utils.websocket import manager
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws/{client_type}/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_type: str,
    client_id: str,
):
    """
    WebSocket endpoint for real-time updates.
    
    Parameters:
    - client_type: Type of client (pos/display)
    - client_id: Unique identifier for the client
    
    Supported message types:
    - ping: Keep-alive message
    - watch_order: Start watching an order
    - unwatch_order: Stop watching an order
    """
    await manager.connect(client_type, client_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            
            elif data.get("type") == "watch_order":
                order_id = data.get("order_id")
                if order_id:
                    manager.add_active_order(client_type, client_id, order_id)
                    logger.info(f"Client {client_type}/{client_id} watching order {order_id}")
            
            elif data.get("type") == "unwatch_order":
                order_id = data.get("order_id")
                if order_id:
                    manager.remove_active_order(client_type, client_id, order_id)
                    logger.info(f"Client {client_type}/{client_id} stopped watching order {order_id}")
            
            else:
                logger.warning(f"Unknown message type from {client_type}/{client_id}: {data}")
                
    except WebSocketDisconnect:
        manager.disconnect(client_type, client_id)
        logger.info(f"Client disconnected: {client_type}/{client_id}")
    except Exception as e:
        logger.error(f"Error in websocket connection {client_type}/{client_id}: {str(e)}")
        manager.disconnect(client_type, client_id) 