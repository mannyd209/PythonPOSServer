# Restaurant POS Backend Documentation

## API Documentation

### Base URL
The API server is automatically discoverable on the local network using Zeroconf/Bonjour.
- Service Type: `_pos._tcp.local.`
- Default Port: 8000

### Authentication
All endpoints except `/health` and `/docs` require authentication via staff PIN codes.
Responses for unauthorized requests:
- 401: Invalid credentials
- 403: Insufficient permissions

### OpenAPI Documentation
- Swagger UI: `http://<server>:8000/docs`
- ReDoc: `http://<server>:8000/redoc`

### API Groups

#### System Administration
Tag: `System Administration`
- System health monitoring
- Service management
- USB device handling
- System logs

#### Authentication
Tag: `Authentication`
- Staff login/logout
- PIN management
- Session handling

#### Catalog Management
Tag: `Catalog`
- Categories and items
  - Category fields: name, sort_order, available
  - Item fields: name, category_id, prices, availability
- Modifiers and options
- Pricing and availability

#### Order Management
Tag: `Orders`
- Order creation and updates
- Status tracking
- History and lookup

#### Payment Processing
Tag: `Payments`
- Card payments via Square
- Refunds
- Payment status

#### Real-time Updates
Tag: `WebSocket`
- Client connections
- Order updates
- Status broadcasts

### Service Discovery Implementation

The backend uses AsyncZeroconf for service broadcasting:

```python
async def register_zeroconf_service():
    local_ip = get_local_ip()
    properties = {
        b'version': b'1.0.0',
        b'api': b'http',
        b'docs': f'http://{local_ip}:{PORT}/docs'.encode('utf-8'),
        b'host': socket.gethostname().encode('utf-8')
    }
    
    info = ServiceInfo(
        "_pos._tcp.local.",
        f"Restaurant POS Server._pos._tcp.local.",
        port=PORT,
        properties=properties,
        addresses=[socket.inet_aton(local_ip)],
        server=f"{socket.gethostname()}.local."
    )
    
    aiozc = AsyncZeroconf()
    await aiozc.async_register_service(info)
    return aiozc, info
```

### Health Check Endpoint

```python
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
    - uptime: Server uptime in seconds
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "uptime": int(datetime.now().timestamp() - startup_time)
    }
```

### Error Responses

All API endpoints follow a consistent error response format:

```json
{
    "detail": "Error message describing what went wrong",
    "code": "ERROR_CODE",
    "timestamp": "2024-01-31T12:34:56.789Z"
}
```

Common HTTP Status Codes:
- 200: Success
- 201: Created
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 422: Validation Error
- 500: Internal Server Error

### Contact Information
- Support URL: https://github.com/yourusername/restaurant-pos/issues
- Email: support@example.com
- License: MIT

1. High-Level Overview

We want to build a Python 3 backend server (running continuously on a Raspberry Pi 4) that handles:

Order Management
Create new orders, store them, track their states (open, closed, refunded, etc.).
Maintain an order history (with date/time, items sold, discounts, tips, payment method, etc.) and allow lookups.
Auto-assign order numbers (1 to 99, then cycle back to 1) with the ability to reset to 1 on demand.
Catalog Management
Manage categories, items, and item modifications (mods).
Basic structure: Category -> Items -> ModLists -> Mods.
Staff Management
Staff name, 4-digit PIN for authentication, hourly rate, hours worked, breaks taken, and sales made by each staff member.
Clock-in and clock-out functionality, even if no one is logged into the POS.
Authentication solely via 4-digit PIN codes.
Discounts & Fees
Discounts with a name, type (percentage or flat), discount amount. A toggle for "global on/off."
Card fee: percentage, base amount, and an on/off toggle.
Tips for card transactions, integrated into final sale calculations and day's report.
Reporting
Real-time daily report:
Cash sales total
Card sales total
Card fees total
Discounts total
Net and gross amounts
Tips received
Must be queryable for any given day, but the typical default is "today."
Connectivity & Network
The server only needs to broadcast on the local network.
The iOS POS front end and iOS Customer Display front end should auto-discover it.
Real-time cart update to the Customer Display front end when items are added/removed in the POS.
Printing & Kitchen Screens
Auto-discovery of receipt printers and kitchen screens on the local network.
Toggles for enabling/disabling receipts and order tickets, sending to kitchen printers or screens.
Ability to reprint old tickets, receipts, or order number tickets.
A toggle for "auto print" or "auto send" for each type of print or screen.
Square Integration
Use Square's SDK/API to handle card transactions.
Square authentication handled via an "Admin Dashboard" app (separate).
The POS app just processes payments using the Square card reader (connected via Bluetooth).
Show status of Square connection on POS settings page.
Refunds should call Square's API as needed.
Data Storage & Reliability
The database will reside on a USB flash drive (not the microSD) for read/write longevity.
The system auto-starts on Raspberry Pi boot or restart, ensuring the USB drive is mounted first.
Must handle large transaction volume reliably (hundreds of orders daily, thousands monthly).
Authentication & Security
Only a 4-digit PIN is required for staff login on the POS.
The Admin Dashboard might have more robust security, but that is a separate app (not covered here).
Architecture & Implementation Notes
Written in Python 3.
Runs as a single "always-on" service (e.g., via systemd or similar).
Must be efficient, stable, and maintainable.
Provide enough detail that the system can be generated automatically without further questions.


2. Technical Stack & Dependencies

Python Framework
Use Flask or FastAPI (whichever is more comfortable for the code generator) to create a RESTful (and/or WebSocket) API.
Database
Use SQLite (most straightforward for running on a Pi and storing on a USB drive).
If you prefer a server-based DB like PostgreSQL, that's also fine; but local SQLite is simpler for a Pi-based kiosk solution.
ORM / Database Migrations
If using Flask, consider SQLAlchemy + Alembic for easy data modeling and migrations.
For FastAPI, SQLModel or "peewee" can also be used.
Real-time Communication
For the Customer Display app, we can use WebSockets or Server-Sent Events (SSE) to send live cart updates.
Square Integration
Use Square's official Python SDK (squareup or squareconnect depending on version).
Provide endpoints to handle OAuth2 tokens or use an API key from the Admin Dashboard.
Printer & Device Discovery
Use a simple UPnP or mDNS/Bonjour approach (e.g., zeroconf in Python) to discover available printers/kitchen screens on the LAN.
For controlling printers or sending raw text, might use libraries like python-escpos, IP-based printing, or direct TCP connections (depending on your printers' protocols).
Raspberry Pi Auto-Start
Use systemd unit files or pm2 (if you want a Node-like manager) or a cron job (@reboot).
Must check USB mount point readiness before launching.


3. Directory & File Structure

A sample structure (assuming Flask + SQLAlchemy + Gunicorn as an example):

pos_backend/
├── app.py                # Entry point for Flask
├── requirements.txt      # Python dependencies
├── config.py             # Configuration (paths to DB on USB, etc.)
├── models/
│   ├── __init__.py
│   ├── base.py           # Base SQLAlchemy, shared metadata
│   ├── user.py           # Staff model
│   ├── order.py          # Orders, order items, line items
│   ├── catalog.py        # Categories, items, mods
│   ├── discount.py       # Discounts, card fees
│   └── ...
├── routes/
│   ├── __init__.py
│   ├── user_routes.py    # Endpoints for staff login, clock in/out
│   ├── order_routes.py   # Endpoints for creating/closing orders
│   ├── catalog_routes.py # Endpoints for managing categories, items, mods
│   ├── discount_routes.py
│   ├── square_routes.py  # Endpoints for Square transactions
│   └── report_routes.py  # Endpoints for daily or historical reports
├── services/
│   ├── printer_service.py    # Handling printer discovery, printing logic
│   ├── kitchen_service.py    # Handling kitchen screen logic
│   ├── square_service.py     # Square API interactions
│   ├── authentication.py     # PIN check logic
│   ├── realtime.py           # Real-time WebSocket or SSE
│   └── ...
├── migrations/           # Alembic migration files (if used)
├── logs/                 # Log files directory
└── ...


4. Configuration

Database Path
Store the SQLite database on the USB drive, e.g., /media/usbdrive/pos_db.sqlite.
The code should check if /media/usbdrive is mounted before proceeding.
Environment Variables (a .env or a config file)
DB_PATH = /media/usbdrive/pos_db.sqlite
SQUARE_ACCESS_TOKEN or a path to credentials if using OAuth
PRINTER_DISCOVERY_ENABLED = True/False
KITCHEN_SCREEN_DISCOVERY_ENABLED = True/False
etc.
Auto-Start
Provide a systemd service file, e.g. pos-backend.service, that:
Waits for USB mount.
Runs gunicorn or uvicorn with the main app.


5. Database Schema / Models

All models in the system use auto-generated IDs. The frontend should never need to provide IDs when creating new records. IDs are returned in the response after successful creation.

### Categories
- `id` (PK): Auto-generated six-digit ID (100000-999999)
- `name` (string): Category name
- `sort_order` (integer): Display order
- `available` (boolean): Availability status

### Items
- `id` (PK): Auto-generated ID
- `name` (string): Item name
- `category_id` (FK): References category.id
- `reg_price` (float): Regular price
- `event_price` (float): Event price
- `sort_order` (integer): Display order
- `available` (boolean): Availability status

### Modifier Lists (ModList)
- `id` (PK): Auto-generated ID
- `name` (string): List name
- `min_selections` (integer): Minimum required selections
- `max_selections` (integer): Maximum allowed selections
- `sort_order` (integer): Display order
- `available` (boolean): Availability status

### Modifiers (Mod)
- `id` (PK): Auto-generated ID
- `mod_list_id` (FK): References mod_list.id
- `name` (string): Modifier name
- `mod_price` (float): Additional price
- `sort_order` (integer): Display order
- `available` (boolean): Availability status

### Staff
- `id` (PK): Auto-generated ID
- `name` (string): Staff name
- `pin` (string): 4-digit PIN (unique)
- `hourly_rate` (float): Pay rate
- `isAdmin` (boolean): Admin privileges
- `is_working` (boolean): Currently clocked in
- `is_on_break` (boolean): Currently on break
- `available` (boolean): Active status

### Staff Shifts
- `id` (PK): Auto-generated ID
- `staff_id` (FK): References staff.id
- `clock_in` (datetime): Start time
- `clock_out` (datetime): End time (nullable)
- `break_start` (datetime): Break start (nullable)
- `break_end` (datetime): Break end (nullable)
- `hourly_rate` (float): Rate for this shift

### Orders
- `id` (PK): Auto-generated ID
- `order_number` (integer): Cycling number (1-99)
- `staff_id` (FK): References staff.id
- `status` (enum): Order status
- `subtotal` (float): Before tax/discounts
- `tax` (float): Tax amount
- `card_fee` (float): Card processing fee
- `total` (float): Final total
- `payment_method` (enum): Cash/Card
- Additional timing fields for tracking status changes

### Order Items
- `id` (PK): Auto-generated ID
- `order_id` (FK): References order.id
- `item_id` (FK): References item.id
- `quantity` (integer): Number of items
- `item_price` (float): Price at time of order
- `mods_price` (float): Total modifications price
- `total_price` (float): Final line item total

### Order Item Modifiers
- `id` (PK): Auto-generated ID
- `order_item_id` (FK): References order_item.id
- `mod_id` (FK): References mod.id
- `mod_price` (float): Price at time of order
- `mod_name` (string): Name at time of order

### Discount Groups
- `id` (PK): Auto-generated ID
- `name` (string): Group name
- `discount_group_id` (integer): Group identifier
- `available` (boolean): Availability status
- `sort_order` (integer): Display order

### Discounts
- `id` (PK): Auto-generated ID
- `group_id` (FK): References discount_group.id
- `name` (string): Discount name
- `amount` (float): Discount amount
- `is_percentage` (boolean): Percentage vs flat
- `sort_order` (integer): Display order
- `available` (boolean): Availability status

### Order Discounts
- `id` (PK): Auto-generated ID
- `order_id` (FK): References order.id
- `discount_id` (FK): References discount.id
- `amount_applied` (float): Actual amount
- `name` (string): Name at time of order

### Card Fee Settings
- `id` (PK): Auto-generated ID
- `available` (boolean): Feature enabled
- `percentage_amount` (float): Fee percentage
- `min_fee` (float): Minimum fee amount

### System Settings
- `id` (PK): Auto-generated ID
- `last_order_reset` (datetime): Last reset
- `timezone` (string): System timezone

### Important Notes for Frontend Development:
1. Never send IDs when creating new records - they are auto-generated by the backend
2. Always use IDs returned from creation endpoints for subsequent operations
3. Category IDs are special - they are always six digits (100000-999999)
4. The order_number field cycles between 1-99 and is managed by the backend
5. When displaying items, always respect the sort_order field
6. All models have an available flag that should be checked before use

6. Endpoints (RESTful + Real-Time)

Below is an outline of the core endpoints. Adjust paths/naming as you prefer.

6.1 Authentication & Staff
POST /auth/login
Body: { "pin": "1234" }
Response: staff info + session token or short-lived JWT.
If minimal security is needed, we might skip JWT and store the staff "logged in" in memory—but better to use a simple token to identify which staff is active.
POST /auth/logout
Ends staff session.
POST /staff/clock_in
Body: { "staff_id": 1 }
Start a new shift.
POST /staff/clock_out
End shift.
POST /staff/break_start / POST /staff/break_end
Manage break intervals.
GET /staff/{id} or GET /staff/list
Retrieve staff info, pins, etc. (In practice, do not return raw PINs to the front end, or store them hashed if security is a concern.)
6.2 Catalog
GET /catalog/categories
Get list of categories.
POST /catalog/categories
Create a new category.
GET /catalog/items (optionally filtered by category)
POST /catalog/items
Create or update an item.
GET /catalog/modifiers
POST /catalog/modifiers
6.3 Discounts & Fees
GET /discounts
POST /discounts
Create or update discount settings.
GET /card_fee
POST /card_fee
Update card fee toggles, percentage, etc.
6.4 Orders
POST /orders
Create a new order.
Body:

{
  "staff_id": 1,
  "items": [
    {
      "item_id": 10,
      "quantity": 2,
      "modifiers": [ { "mod_id": 5 }, { "mod_id": 7 } ]
    }
  ],
  "discount_id": 2
}

Assign next available order_number (1..99).
PUT /orders/{order_id}/add_item
PUT /orders/{order_id}/remove_item
POST /orders/{order_id}/close
Body might contain payment details, e.g., method=cash/card, cash_tendered, tips, etc.
GET /orders/{order_id}
GET /orders (with filters, e.g., date range)
POST /orders/{order_id}/refund
Should integrate with Square's API if card payment.
Mark the order in DB as refunded or partially refunded.
6.5 Reporting
GET /reports/daily (default: today)
Return JSON with sums of:
total_sales_gross
total_sales_net
card_sales
cash_sales
card_fees
discounts_applied
tips_received
GET /reports/{date} or GET /reports/range?start=YYYY-MM-DD&end=YYYY-MM-DD
6.6 Square Integration
POST /square/charge
Called from POS to process a card payment.
Body: amount, order_id, etc.
Square's Python SDK handles the transaction.
Return success or error.
GET /square/connection_status
Indicate if we have a valid Square token, reader is connected, etc.
6.7 Printing & Kitchen Screens
GET /printers/discover
Return list of discovered printers, addresses, capabilities.
POST /printers/select
Body: the chosen printer for receipts, order tickets, etc.
POST /printers/print_receipt
Body: order_id, or a raw text/HTML.
POST /kitchen_screens/discover
Return discovered kitchen displays.
POST /kitchen_screens/select
Choose which screen to send orders to.
POST /kitchen_screens/send_order
Send the order details to the chosen screen(s).


7. Real-Time Cart (Customer Display)

Use WebSockets or SSE to broadcast cart updates in real time.
For example, whenever POST /orders or PUT /orders/{id}/add_item is called, broadcast an event:

{
  "event": "cart_updated",
  "data": {
    "order_id": 123,
    "items": [...],
    "total": 19.99
  }
}

The Customer Display iOS app listens for these messages and updates the screen accordingly.


8. Order Number Cycling

Keep a persistent counter for the next order number.
When an order is created, set order_number = currentCounter, then increment by 1.
If currentCounter > 99, reset it to 1.
Provide a function or endpoint to reset the counter (e.g., for a new day or a manual reset).


9. Auto-Run on Raspberry Pi with USB Mount Check

Script: start_server.sh
Checks if /media/usbdrive is mounted. If not, wait or mount automatically.
Then run gunicorn app:app --bind 0.0.0.0:5000 (or uvicorn main:app --host 0.0.0.0 --port 5000 if using FastAPI).
Systemd Unit File: /etc/systemd/system/pos-backend.service
[Unit]
Description=POS Backend Service
After=network.target usb-mount.service

[Service]
ExecStart=/path/to/pos_backend/start_server.sh
WorkingDirectory=/path/to/pos_backend
Restart=always
User=pi
Group=pi

[Install]
WantedBy=multi-user.target
Make sure usb-mount.service is a service or logic that ensures your USB drive is ready.
Enable:
sudo systemctl enable pos-backend.service
sudo systemctl start pos-backend.service
Logging:
Direct logs to /var/log/pos_backend.log or store them in pos_backend/logs/.


10. Efficiency & Reliability

Connection Pooling (if using something heavier than SQLite, e.g. Postgres).
Error Handling in each route, with structured JSON error responses.
Logging of all major events (staff actions, order creation, refunds, etc.).
Health Checks: Provide a simple endpoint like GET /health returning "OK" if the service is up.


11. Testing & Deployment

Automated Tests
Unit tests for each route (create order, close order, apply discount, etc.).
Possibly integration tests with a real Square sandbox environment.
Deployment Steps
Copy code to Pi, install dependencies: pip install -r requirements.txt.
Set up the DB on USB: python -m alembic upgrade head or create initial schema.
Enable and start the systemd service.
Confirm logs or check with curl http://localhost:5000/health.


12. Summary of Requirements

Ensure the final code includes:

All Models: Staff, Shifts, Category, Item, Modifier, Discount, CardFee, Order, OrderItem, (optional) OrderItemModifier.
All Endpoints: For staff authentication, clock in/out, order operations, discounts, fees, real-time updates, daily reports, printing, Square card processing, etc.
Real-Time Cart Mechanism: Possibly WebSocket or SSE events.
Printer & Kitchen Screen Discovery: Using something like zeroconf.
Systemd Startup: Checking the USB is mounted, then launching the server.
Cycle Order Numbers: 1–99, then back to 1, plus a reset function.