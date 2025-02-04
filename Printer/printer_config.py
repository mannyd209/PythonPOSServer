# Network settings
HOST = '0.0.0.0'
PORT = 9100
KDS_PORT = 9104
PHYSICAL_PRINTER_PORT = 9100

# Printer emulation settings
PRINTER_ID = {
    'MANUFACTURER': b'EPSON',
    'MODEL': b'TM-T88V',
    'FIRMWARE': b'1.23',
    'SERIAL': b'123456789'
}

def update_printer_ips(kds_ip=None, printer_ip=None):
    """Update printer IPs - called by settings route when IPs are changed"""
    global KDS_IP, PHYSICAL_PRINTER_IP
    
    if kds_ip:
        KDS_IP = kds_ip
    if printer_ip:
        PHYSICAL_PRINTER_IP = printer_ip
