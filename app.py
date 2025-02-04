from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
import logging
from datetime import datetime
from config import HOST, PORT, SQUARE_ACCESS_TOKEN
from models import get_db, Base
from models.base import engine
from routes import auth, catalog, order, payment, websocket, admin, staff, staff_time, discount
from utils.square import check_connection
from utils.websocket import manager
import os
from zeroconf import ServiceInfo, Zeroconf
import socket
import asyncio
from sqlalchemy import inspect
from zeroconf.asyncio import AsyncZeroconf

# Setup logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/pos_backend.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Function to check if database is initialized
def is_database_initialized():
    try:
        # Check if database directory exists
        db_path = os.getenv('DB_PATH', '/media/usbdrive/pos_data/pos_db.sqlite')
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir):
            logger.warning(f"Database directory {db_dir} does not exist")
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created database directory {db_dir}")
        
        # Check if any tables exist
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        return len(existing_tables) > 0
    except Exception as e:
        logger.error(f"Error checking database initialization: {e}")
        return False

# Function to get local IP address
def get_local_ip():
    try:
        # Try getting the IP by creating a temporary socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't actually connect but gets the default route
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logger.error(f"Error getting local IP: {str(e)}")
        # Fallback to localhost if we can't get the network IP
        return '127.0.0.1'

# Zeroconf service registration
async def register_zeroconf_service():
    try:
        # Get local IP using the new method
        local_ip = get_local_ip()
        logger.info(f"Using local IP address: {local_ip}")
        
        # Convert IP string to bytes
        ip_bytes = socket.inet_aton(local_ip)
        logger.info(f"IP bytes: {ip_bytes}")
        
        # Create service info with correct parameter format
        service_type = "_pos._tcp.local."
        service_name = f"Restaurant POS Server.{service_type}"
        
        # Create properties as bytes dictionary
        properties = {
            b'version': b'1.0.0',
            b'api': b'http',
            b'docs': f'http://{local_ip}:{PORT}/docs'.encode('utf-8'),
            b'host': socket.gethostname().encode('utf-8')
        }
        
        # Create service info
        info = ServiceInfo(
            service_type,  # type_
            service_name,  # name
            port=PORT,
            properties=properties,
            addresses=[ip_bytes],
            server=f"{socket.gethostname()}.local."
        )
        logger.info(f"Created ServiceInfo object: {info}")
        
        # Initialize AsyncZeroconf
        aiozc = AsyncZeroconf()
        logger.info("Initialized AsyncZeroconf object")
        
        # Register service using the correct async method
        await aiozc.async_register_service(info)
        logger.info(f"Successfully registered zeroconf service: {info.name} at {local_ip}:{PORT}")
        
        return aiozc, info
    except Exception as e:
        error_msg = f"Failed to register zeroconf service: {str(e)}"
        logger.error(error_msg)
        logger.exception("Full traceback:")
        raise Exception(error_msg)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting POS Backend Server...")
    
    # Initialize database tables only if they don't exist
    try:
        if not is_database_initialized():
            logger.info("Initializing database tables for the first time...")
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")
        else:
            logger.info("Database already initialized")
    except Exception as e:
        logger.error(f"Failed to handle database initialization: {e}")
        raise
    
    # Register zeroconf service
    aiozc = None
    service_info = None
    try:
        aiozc, service_info = await register_zeroconf_service()
        logger.info("Zeroconf service registered successfully")
    except Exception as e:
        logger.error(f"Failed to register zeroconf service: {str(e)}")
    
    # Check Square connection
    if not SQUARE_ACCESS_TOKEN:
        logger.warning("Square access token not configured")
    else:
        try:
            status = check_connection()
            if status["status"] == "connected":
                logger.info(f"Connected to Square API ({status['environment']})")
            else:
                logger.error(f"Failed to connect to Square API: {status.get('error')}")
        except Exception as e:
            logger.error(f"Error checking Square connection: {e}")
    
    # Initialize WebSocket manager
    logger.info("WebSocket manager initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down POS Backend Server...")
    
    # Unregister zeroconf service
    if aiozc and service_info:
        try:
            await aiozc.async_unregister_service(service_info)
            await aiozc.async_close()
            logger.info("Unregistered zeroconf service")
        except Exception as e:
            logger.error(f"Error unregistering zeroconf service: {e}")
    
    # Close all WebSocket connections
    for client_type in manager.connections:
        for client_id in list(manager.connections[client_type].keys()):
            manager.disconnect(client_type, client_id)
    logger.info("All WebSocket connections closed")

def custom_openapi():
    """Generate custom OpenAPI schema"""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Restaurant POS API",
        version="1.0.0",
        description="""
        # Restaurant Point of Sale System API

        This API provides a comprehensive backend solution for restaurant management, featuring:

        ## ID Generation
        - All IDs are auto-generated by the backend
        - Never send IDs when creating new records
        - Use IDs returned from creation endpoints for subsequent operations
        - Category IDs are special: always six digits (100000-999999)
        - Order numbers cycle between 1-99 and are managed by the backend

        ## Core Features
        - 🔐 Staff Authentication (4-digit PIN)
        - ⏰ Staff Time Tracking & Breaks
        - 📋 Order Processing & Management
        - 🍽️ Menu & Catalog Management
        - 💳 Payment Processing (Cash/Card)
        - 🔄 Real-time Updates via WebSocket
        - ⚙️ System Administration
        
        ## Key Capabilities
        - Simple PIN-based authentication (4-digit PIN)
        - Admin privileges controlled by isAdmin flag
        - Comprehensive time tracking:
          - Clock in/out functionality
        - Break management
          - Earnings calculation
          - Real-time status updates
        - Structured menu management:
          - Categories (auto-generated 6-digit IDs)
          - Items with regular/event pricing
          - Mod lists with min/max selections
          - Individual mods with optional pricing
        - Real-time order tracking and updates
        - Integrated payment processing
        - WebSocket support for real-time updates
        
        ## Server Discovery
        The POS server uses Zeroconf (Bonjour) for automatic discovery:
        - Service Type: _pos._tcp.local.
        - Properties include version, API endpoint, and documentation URL

        ## Getting Started
        1. Discover server using Zeroconf
        2. Authenticate using 4-digit PIN
        3. Include PIN in X-Staff-PIN header for all requests
        4. Connect to WebSocket with PIN parameter
        5. Admin operations require PIN of staff with isAdmin=true

        ## Best Practices
        - Never send IDs when creating new records
        - Always use IDs returned from creation endpoints
        - Keep PINs secure and private
        - Handle permission errors appropriately
        - Use secure HTTPS in production
        - Implement automatic reconnection for WebSocket
        
        For detailed documentation, visit our [API Documentation](/redoc).
        For support, contact support@example.com
        """,
        routes=app.routes
    )

    # Add tags metadata
    openapi_schema["tags"] = [
        {
            "name": "Authentication",
            "description": "Staff authentication using 4-digit PIN"
        },
        {
            "name": "Staff Time",
            "description": "Clock in/out operations and break management"
        },
        {
            "name": "Staff Management",
            "description": "Staff member administration (requires admin PIN)"
        },
        {
            "name": "Catalog",
            "description": """Menu management with:
            - Categories (auto-generated 6-digit IDs)
            - Items (auto-generated IDs)
            - Mod lists (auto-generated IDs)
            - Individual mods (auto-generated IDs)
            (Requires admin PIN for modifications)"""
        },
        {
            "name": "Orders",
            "description": "Order creation and management (auto-generated IDs, cycling order numbers 1-99)"
        },
        {
            "name": "Payments",
            "description": "Payment processing (requires staff PIN)"
        },
        {
            "name": "Discounts",
            "description": "Discount management (auto-generated IDs, requires staff PIN, some operations require admin)"
        },
        {
            "name": "System Administration",
            "description": "System settings and maintenance (requires admin PIN)"
        },
        {
            "name": "WebSocket",
            "description": "Real-time updates (requires valid PIN in connection URL)"
        }
    ]

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "staffPin": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Staff-PIN",
            "description": "4-digit staff PIN"
        }
    }

    # Add global security requirement
    openapi_schema["security"] = [{"staffPin": []}]

    # Add response components
    openapi_schema["components"]["responses"] = {
        "InvalidPINError": {
            "description": "Invalid PIN format or PIN not found",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": False},
                            "error": {
                                "type": "object",
                                "properties": {
                                    "code": {"type": "string", "example": "invalid_pin"},
                                    "message": {"type": "string", "example": "Invalid PIN provided"}
                                }
                            }
                        }
                    }
                }
            }
        },
        "AdminRequiredError": {
            "description": "Operation requires admin privileges",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": False},
                            "error": {
                                "type": "object",
                                "properties": {
                                    "code": {"type": "string", "example": "admin_required"},
                                    "message": {"type": "string", "example": "This operation requires admin privileges"}
                                }
                            }
                        }
                    }
                }
            }
        },
        "AlreadyClockedInError": {
            "description": "Staff member is already clocked in",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": False},
                            "error": {
                                "type": "object",
                                "properties": {
                                    "code": {"type": "string", "example": "already_clocked_in"},
                                    "message": {"type": "string", "example": "Staff member is already clocked in"}
                                }
                            }
                        }
                    }
                }
            }
        },
        "NotClockedInError": {
            "description": "Staff member is not clocked in",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": False},
                            "error": {
                                "type": "object",
                                "properties": {
                                    "code": {"type": "string", "example": "not_clocked_in"},
                                    "message": {"type": "string", "example": "Staff member is not clocked in"}
                                }
                            }
                        }
                    }
                }
            }
        },
        "AlreadyOnBreakError": {
            "description": "Staff member is already on break",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": False},
                            "error": {
                                "type": "object",
                                "properties": {
                                    "code": {"type": "string", "example": "already_on_break"},
                                    "message": {"type": "string", "example": "Staff member is already on break"}
                                }
                            }
                        }
                    }
                }
            }
        },
        "NotOnBreakError": {
            "description": "Staff member is not on break",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": False},
                            "error": {
                                "type": "object",
                                "properties": {
                                    "code": {"type": "string", "example": "not_on_break"},
                                    "message": {"type": "string", "example": "Staff member is not on break"}
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Initialize FastAPI with custom configuration
app = FastAPI(
    title="Restaurant POS Backend",
    description="Backend server for the Restaurant Point of Sale System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,  # Disable default docs
    redoc_url=None  # Disable default redoc
)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom documentation endpoints with modern UI
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Restaurant POS API Documentation",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        swagger_favicon_url="/static/favicon.png",
        oauth2_redirect_url="/docs/oauth2-redirect",
        init_oauth={
            "usePkceWithAuthorizationCodeGrant": True,
            "persistAuthorization": True
        },
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,  # Hide schemas section by default
            "displayRequestDuration": True,   # Show request duration
            "filter": True,                   # Enable filtering
            "tryItOutEnabled": True,          # Enable Try it out by default
            "syntaxHighlight": {
                "activate": True,
                "theme": "monokai"
            }
        }
    )

@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="Restaurant POS API Documentation",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
        redoc_favicon_url="/static/favicon.png",
        with_google_fonts=True,
        redoc_options={
            "hideDownloadButton": True,
            "expandResponses": "200,201",
            "pathInMiddlePanel": True,
            "showExtensions": True,
            "sortPropsAlphabetically": True
        }
    )

# Register routes with proper prefixes and tags
app.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

app.include_router(
    staff_time.router,
    prefix="/staff",
    tags=["Staff Time"]
)

app.include_router(
    staff.router,
    prefix="/staff/admin",
    tags=["Staff Management"]
)

app.include_router(
    catalog.router,
    prefix="/catalog",
    tags=["Catalog"]
)

app.include_router(
    order.router,
    prefix="/orders",
    tags=["Orders"]
)

app.include_router(
    payment.router,
    prefix="/payments",
    tags=["Payments"]
)

app.include_router(
    discount.router,
    prefix="/discounts",
    tags=["Discounts"]
)

app.include_router(
    websocket.router,
    prefix="/ws",
    tags=["WebSocket"]
)

app.include_router(
    admin.router,
    prefix="/admin",
    tags=["System Administration"]
)

# Custom OpenAPI schema
app.openapi = custom_openapi

# Health check endpoint
@app.get(
    "/health",
    tags=["System"],
    summary="System Health Check",
    response_description="Current system health status"
)
async def health_check():
    """
    Check the health status of the API server.

    Returns:
    - status: Current server status (healthy/unhealthy)
    - timestamp: Current UTC timestamp
    - version: API version
    - database: Database connection status
    - websocket: WebSocket manager status
    """
    try:
        # Check database connection
        db = next(get_db())
        db_status = "connected"
        db.close()
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "database": db_status,
        "websocket": {
            "active_connections": sum(len(conns) for conns in manager.connections.values())
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=HOST,
        port=PORT,
        reload=False,
        workers=1,
        log_level="info"
    ) 