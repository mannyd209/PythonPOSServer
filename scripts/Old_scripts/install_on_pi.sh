#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Error handling
set -e
trap 'echo -e "${RED}An error occurred. Installation failed.${NC}"; exit 1' ERR

# Function to check command status
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $1 successful${NC}"
    else
        echo -e "${RED}✗ $1 failed${NC}"
        exit 1
    fi
}

echo -e "${GREEN}Starting POS Backend installation...${NC}"

# Check OS version
echo -e "${YELLOW}Checking Raspberry Pi OS version...${NC}"
if ! grep -q "Debian GNU/Linux 12" /etc/os-release; then
    echo -e "${RED}Error: This script requires Raspberry Pi OS Bookworm (Debian 12)${NC}"
    echo -e "${RED}Please update your system to the latest version${NC}"
    exit 1
fi

# Check architecture
echo -e "${YELLOW}Checking system architecture...${NC}"
if [ "$(uname -m)" != "aarch64" ]; then
    echo -e "${RED}Error: This script requires 64-bit ARM architecture${NC}"
    echo -e "${RED}Please install Raspberry Pi OS 64-bit${NC}"
    exit 1
fi

# Update system
echo -e "${YELLOW}Updating system packages...${NC}"
sudo apt update
# Check for available updates
UPDATES=$(sudo apt list --upgradable 2>/dev/null | grep -c "upgradable" || echo "0")
if [ "$UPDATES" -gt 0 ]; then
    echo -e "${YELLOW}Installing $UPDATES package updates...${NC}"
    sudo apt upgrade -y
fi
check_status "System update"

# Wait a moment for any package processes to finish
sleep 2

# Install required repositories
echo -e "${YELLOW}Adding required repositories...${NC}"
if ! grep -q "non-free" /etc/apt/sources.list; then
    sudo sed -i 's/main/main non-free/g' /etc/apt/sources.list
    sudo apt update || true
fi
check_status "Repository setup"

# Wait for dpkg locks to clear
echo -e "${YELLOW}Waiting for package system...${NC}"
while sudo fuser /var/lib/dpkg/lock >/dev/null 2>&1 || sudo fuser /var/lib/apt/lists/lock >/dev/null 2>&1; do
    echo -n "."
    sleep 1
done

# Install required system packages
echo -e "${YELLOW}Installing required system packages...${NC}"
sudo apt install -y \
    python3-pip python3-venv python3-dev python3.11-dev \
    build-essential git avahi-daemon exfatprogs \
    python3.11-minimal libpython3.11-dev cython3 \
    libffi-dev libssl-dev pkg-config \
    libjpeg-dev zlib1g-dev libfreetype6-dev liblcms2-dev \
    libopenjp2-7-dev libtiff5-dev libwebp-dev
check_status "Package installation"

# Verify Python version
echo -e "${YELLOW}Verifying Python version...${NC}"
PYTHON_VERSION=$(python3 --version)
if [[ ! "$PYTHON_VERSION" =~ "Python 3.11" ]]; then
    echo -e "${RED}Error: Python 3.11 is required${NC}"
    echo -e "${RED}Found: $PYTHON_VERSION${NC}"
    exit 1
fi
check_status "Python version check"

# Optimize RPi4 settings for 64-bit lite with USB 3.0
echo -e "${YELLOW}Optimizing RPi4 settings...${NC}"

# Set GPU memory in config.txt
echo -e "${YELLOW}Setting GPU memory...${NC}"
if ! grep -q "^gpu_mem=" /boot/config.txt; then
    echo "gpu_mem=16" | sudo tee -a /boot/config.txt
else
    sudo sed -i 's/^gpu_mem=.*/gpu_mem=16/' /boot/config.txt
fi

# Set CPU governor to performance
echo -e "${YELLOW}Setting CPU governor...${NC}"
echo "performance" | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Optimize USB settings in config.txt
echo -e "${YELLOW}Optimizing USB settings...${NC}"
CONFIG_UPDATES=(
    "dtoverlay=dwc2,dr_mode=host"
    "max_usb_current=1"
    "dtparam=sd_poll_once=on"
)

for setting in "${CONFIG_UPDATES[@]}"; do
    if ! grep -q "^$setting" /boot/config.txt; then
        echo "$setting" | sudo tee -a /boot/config.txt
    fi
done

check_status "RPi4 optimization"

# Optimize system settings for database on USB 3.0
echo -e "${YELLOW}Optimizing system settings for USB 3.0 storage...${NC}"
cat << EOF | sudo tee /etc/sysctl.d/99-usb-storage.conf
# Increase read-ahead for USB storage
vm.vfs_cache_pressure=50
vm.dirty_background_ratio=5
vm.dirty_ratio=10
EOF
sudo sysctl -p /etc/sysctl.d/99-usb-storage.conf
check_status "System optimization"

# Setup Python virtual environment
echo -e "${YELLOW}Setting up Python virtual environment...${NC}"
cd /home/pos/AppPOS
python3 -m venv venv
source venv/bin/activate
check_status "Virtual environment creation"

# Install Python dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install psutil
pip install -r requirements.txt
check_status "Python dependencies installation"

# Verify USB drive mount point
echo -e "${YELLOW}Verifying USB drive mount point...${NC}"
if [ ! -d "/media/usbdrive" ]; then
    sudo mkdir -p /media/usbdrive
fi
sudo chown -R pos:pos /media/usbdrive
check_status "USB mount point verification"

# Create data directories if they don't exist
echo -e "${YELLOW}Creating data directories...${NC}"
mkdir -p /media/usbdrive/pos_data /media/usbdrive/backups
check_status "Directory creation"

# Initialize the database
echo -e "${YELLOW}Initializing database...${NC}"
export DB_PATH="/media/usbdrive/pos_data/pos_db.sqlite"
export DB_BACKUP_PATH="/media/usbdrive/backups"
python -c "from models.base import Base, engine; Base.metadata.create_all(bind=engine)"
check_status "Database initialization"

# Create backend service
echo -e "${YELLOW}Creating backend service...${NC}"
cat << EOF | sudo tee /etc/systemd/system/pos-backend.service
[Unit]
Description=Restaurant POS Backend Service
After=network.target network-online.target
Wants=network-online.target
StartLimitIntervalSec=500
StartLimitBurst=5

[Service]
Type=simple
User=pos
Group=pos
WorkingDirectory=/home/pos/AppPOS
Environment="PATH=/home/pos/AppPOS/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="DB_PATH=/media/usbdrive/pos_data/pos_db.sqlite"
Environment="DB_BACKUP_PATH=/media/usbdrive/backups"
Environment="PYTHONOPTIMIZE=1"
Environment="PYTHONUNBUFFERED=1"

ExecStart=/home/pos/AppPOS/venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8000 --workers 2 --loop uvloop

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
check_status "Service creation"

# Setup sudo permissions
echo -e "${YELLOW}Setting up sudo permissions...${NC}"
cat << EOF | sudo tee /etc/sudoers.d/pos-backend
# Allow pos-backend service to manage system
pos ALL=(ALL) NOPASSWD: /bin/systemctl restart pos-backend.service
pos ALL=(ALL) NOPASSWD: /bin/systemctl stop pos-backend.service
pos ALL=(ALL) NOPASSWD: /bin/systemctl start pos-backend.service
pos ALL=(ALL) NOPASSWD: /bin/systemctl status pos-backend.service
pos ALL=(ALL) NOPASSWD: /sbin/shutdown
pos ALL=(ALL) NOPASSWD: /usr/bin/vcgencmd
EOF
sudo chmod 440 /etc/sudoers.d/pos-backend
check_status "Permissions setup"

# Create Avahi service definition
echo -e "${YELLOW}Creating Avahi service definition...${NC}"
cat << EOF | sudo tee /etc/avahi/services/pos-backend.service
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">POS Backend on %h</name>
  <service>
    <type>_http._tcp</type>
    <subtype>_pos._sub._http._tcp</subtype>
    <port>8000</port>
    <txt-record>path=/</txt-record>
    <txt-record>version=1.0</txt-record>
  </service>
</service-group>
EOF
check_status "Avahi service definition"

# Restart Avahi daemon to apply changes
echo -e "${YELLOW}Restarting Avahi daemon...${NC}"
sudo systemctl restart avahi-daemon
sleep 2  # Give Avahi time to start advertising
check_status "Avahi daemon restart"

# Start the service
echo -e "${YELLOW}Starting POS backend service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable pos-backend
sudo systemctl start pos-backend

# Wait for service to be active
echo -e "${YELLOW}Waiting for backend service to be active...${NC}"
for i in {1..30}; do
    if systemctl is-active --quiet pos-backend; then
        echo -e "${GREEN}Backend service started successfully${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}Failed to start backend service. Checking logs...${NC}"
        journalctl -u pos-backend --no-pager -n 50
        exit 1
    fi
    echo -n "."
    sleep 1
done

echo -e "${GREEN}Installation complete!${NC}"
echo -e "\nService Status:"
systemctl status pos-backend --no-pager

echo -e "\nAPI should be available at: http://$(hostname -I | awk '{print $1}'):8000"
echo -e "Check the API documentation at: http://$(hostname -I | awk '{print $1}'):8000/docs"
