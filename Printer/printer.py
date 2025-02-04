from datetime import datetime
import socket
import json
import logging
import pytz
from importlib import reload
from . import printer_config

# Set timezone
TIMEZONE = pytz.timezone('America/Los_Angeles')

# Printer commands
INIT_PRINTER = b'\x1b\x40'
CENTER_ALIGN = b'\x1b\x61\x01'
LEFT_ALIGN = b'\x1b\x61\x00'
LARGEST_SIZE = b'\x1d\x21\x33'  # Quadruple height and width
BOLD_ON = b'\x1b\x45\x01'
NORMAL_SIZE = b'\x1d\x21\x00'
CUT_PAPER = b'\x1d\x56\x41'
OPEN_DRAWER = b'\x1b\x70\x00\x19\xfa'
LINE_FEEDS = b'\n'
TINY_SPACE = b''
SMALL_SPACE = b'\n'
MEDIUM_SPACE = b'\n\n'
LARGE_SPACE = b'\n\n\n'
EXTRA_LARGE_SPACE = b'\n\n\n\n'

def send_to_physical_printer(order_number, datetime_str=None):
    """Send formatted order number to physical Epson printer"""
    try:
        # Reload printer_config to get latest settings
        reload(printer_config)
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as printer:
            printer.settimeout(5)  # 5 second timeout
            printer.connect((printer_config.PHYSICAL_PRINTER_IP, printer_config.PHYSICAL_PRINTER_PORT))
            
            # Format current time if not provided
            if not datetime_str:
                dt = datetime.now(TIMEZONE)
            else:
                # Parse the datetime string and assume it's already in local time
                dt = datetime.strptime(datetime_str.strip(), "%m/%d/%y, %I:%M:%S %p")
                dt = TIMEZONE.localize(dt)
            
            formatted_time = dt.strftime('%b %d, %Y  %I:%M:%S %p')

            print_data = b''.join([
                INIT_PRINTER,
                CENTER_ALIGN,
                BOLD_ON,
                NORMAL_SIZE,
                TINY_SPACE,
                "WING IT ON WHEELS\n".encode(),
                EXTRA_LARGE_SPACE,
                LARGEST_SIZE,
                f"ORDER\n#{order_number}\n".encode(),
                NORMAL_SIZE,
                EXTRA_LARGE_SPACE,
                formatted_time.encode() + b'\n',
                TINY_SPACE,
                CUT_PAPER,
                OPEN_DRAWER
            ])
            
            printer.sendall(print_data)
            logging.info(f"Order #{order_number} sent to physical printer at {printer_config.PHYSICAL_PRINTER_IP}")
            
    except Exception as e:
        logging.error(f"Failed to print to physical printer at {printer_config.PHYSICAL_PRINTER_IP}: {e}")
        raise

def send_to_kds(order_number, items, staff_name=None, datetime_str=None):
    """Send order to KDS"""
    try:
        # Reload printer_config to get latest settings
        reload(printer_config)
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as kds_socket:
            kds_socket.settimeout(5)  # 5 second timeout
            kds_socket.connect((printer_config.KDS_IP, printer_config.KDS_PORT))
            
            # Convert datetime to epoch milliseconds
            if datetime_str:
                naive_dt = datetime.strptime(datetime_str.strip(), "%m/%d/%y, %I:%M:%S %p")
                dt = TIMEZONE.localize(naive_dt)
            else:
                dt = datetime.now(TIMEZONE)
            
            order_time_ms = int(dt.timestamp() * 1000)
            
            # Filter out discounts and format remaining items for KDS
            kds_items = []
            for item in items:
                if not item.get('isDiscount', False):  # Skip items that are discounts
                    kds_item = {
                        "name": item['name'],
                        "qty": item['quantity'],
                        "notes": item.get('notes', ''),
                        "mods": []
                    }
                    # Format modifiers with prices
                    for mod in item.get('mods', []):
                        mod_text = mod['name']
                        if mod.get('price', 0) > 0:
                            mod_text += f" (+${mod['price']:.2f})"
                        kds_item["mods"].append(mod_text)
                    kds_items.append(kds_item)
            
            # Generate order ID for KDS (2-digit order number + 2 random letters)
            import random
            import string
            random_letters = ''.join(random.choices(string.ascii_uppercase, k=2))
            kds_id = f"{str(order_number).zfill(2)}{random_letters}"
            
            order_data = {
                "command": "create-order",
                "order": {
                    "id": kds_id,
                    "name": f"#{str(order_number).zfill(2)}",  # Pad to 2 digits
                    "time": order_time_ms,
                    "mode": "For Here",
                    "items": kds_items,
                    "server": staff_name
                }
            }
            
            kds_socket.sendall(json.dumps(order_data).encode('utf-8'))
            logging.info(f"Order #{order_number} sent to KDS at {printer_config.KDS_IP}")
            
    except Exception as e:
        logging.error(f"Failed to send to KDS at {printer_config.KDS_IP}: {e}")
        raise

def print_receipt(order_number, items, subtotal, tax, total, payment_method=None, card_fee=0.00, amount_tendered=None, change=None, datetime_str=None):
    """Print a detailed receipt to the physical printer"""
    try:
        # Reload printer_config to get latest settings
        reload(printer_config)
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as printer:
            printer.connect((printer_config.PHYSICAL_PRINTER_IP, printer_config.PHYSICAL_PRINTER_PORT))
            
            # Format current time if not provided
            if not datetime_str:
                dt = datetime.now(TIMEZONE)
            else:
                # Parse the datetime string and assume it's already in local time
                dt = datetime.strptime(datetime_str.strip(), "%m/%d/%y, %I:%M:%S %p")
                dt = TIMEZONE.localize(dt)
            
            formatted_time = dt.strftime('%b %d, %Y  %I:%M:%S %p')

            # Build the receipt content
            receipt_lines = [
                INIT_PRINTER,
                CENTER_ALIGN,
                BOLD_ON,
                "WING IT ON WHEELS\n".encode(),
                SMALL_SPACE,
                f"Order #{str(order_number).zfill(2)}\n".encode(),  # Pad to 2 digits
                formatted_time.encode() + b'\n',
                MEDIUM_SPACE,
                LEFT_ALIGN,
            ]

            # Add items
            for item in items:
                # Item name and quantity
                item_line = f"{item['name']} x{item['quantity']}\n".encode()
                receipt_lines.append(item_line)
                
                # Item price
                price = item['total_price']  # Use total_price which includes mods
                price_line = f"   ${price:.2f}\n".encode()
                receipt_lines.append(price_line)

                # Add notes if present
                if item.get('notes'):
                    notes_line = f"   Note: {item['notes']}\n".encode()
                    receipt_lines.append(notes_line)

                # Modifiers
                for mod in item.get('mods', []):
                    mod_line = f"   + {mod['name']}"
                    if mod.get('price', 0) > 0:
                        mod_line += f" (+${mod['price']:.2f})"
                    mod_line += "\n"
                    receipt_lines.append(mod_line.encode())

                receipt_lines.append(SMALL_SPACE)

            # Add totals section
            receipt_lines.extend([
                MEDIUM_SPACE,
                CENTER_ALIGN,
                "------------------------\n".encode(),
                f"Subtotal: ${subtotal:.2f}\n".encode(),
                f"Tax: ${tax:.2f}\n".encode(),
            ])

            # Add card fee if applicable
            if payment_method == PaymentMethod.CARD and card_fee > 0:
                receipt_lines.append(f"Card Fee: ${card_fee:.2f}\n".encode())

            # Add final total
            receipt_lines.append(f"Total: ${total:.2f}\n".encode())

            # Add tender and change for cash transactions
            if amount_tendered is not None:
                receipt_lines.extend([
                    f"Tendered: ${amount_tendered:.2f}\n".encode(),
                    f"Change: ${change:.2f}\n".encode(),
                ])

            # Add payment method
            if payment_method:
                receipt_lines.append(f"Paid by: {payment_method.value}\n".encode())

            # Add footer
            receipt_lines.extend([
                MEDIUM_SPACE,
                "Thank You!\n".encode(),
                "Please Come Again\n".encode(),
                MEDIUM_SPACE,
                b'\n\n',  # Feed paper to ensure complete printing
                CUT_PAPER,
                INIT_PRINTER  # Reset printer state
            ])

            # Send the receipt
            printer.sendall(b''.join(receipt_lines))
            logging.info(f"Receipt for order #{order_number} printed successfully to {printer_config.PHYSICAL_PRINTER_IP}")
            
    except Exception as e:
        logging.error(f"Failed to print receipt to {printer_config.PHYSICAL_PRINTER_IP}: {e}")
        raise