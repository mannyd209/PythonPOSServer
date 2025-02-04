#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Error handling
set -e
trap 'echo -e "${RED}An error occurred. Deployment failed.${NC}"; exit 1' ERR

# Set Raspberry Pi details
PI_HOST="pos.local"
PI_HOSTNAME="pos"

# Configuration
PI_USER="pos"
PROJECT_DIR="/Volumes/MacSSD/AppPOS"
REMOTE_DIR="/home/${PI_USER}/AppPOS"

# Verify hostname matches
if ! ssh ${PI_USER}@${PI_HOST} "[ \$(hostname) = ${PI_HOSTNAME} ]"; then
    echo -e "${RED}Error: Hostname mismatch. Expected '${PI_HOSTNAME}'${NC}"
    exit 1
fi

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}Please do not run as root${NC}"
    exit 1
fi

# Verify USB drive is formatted
if [ ! -d "/Volumes/POS_DATA" ]; then
    echo -e "${RED}USB drive not found at /Volumes/POS_DATA${NC}"
    echo -e "${YELLOW}Please run ./scripts/format_usb_mac.sh first${NC}"
    exit 1
fi

# Make scripts executable
chmod +x "${PROJECT_DIR}/scripts/"*.sh

# Function to check if Pi is accessible
check_pi_connection() {
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}Waiting for Pi to become accessible...${NC}"
    while [ $attempt -le $max_attempts ]; do
        if ping -c 1 $PI_HOST >/dev/null 2>&1; then
            echo -e "${GREEN}Pi is accessible!${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo -e "\n${RED}Failed to connect to Pi after $max_attempts attempts${NC}"
    return 1
}

# Function to check command status
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $1 successful${NC}"
    else
        echo -e "${RED}✗ $1 failed${NC}"
        exit 1
    fi
}

# Function to verify SSH connection
verify_ssh() {
    echo -e "${YELLOW}Verifying SSH connection...${NC}"
    if ! ssh -q ${PI_USER}@${PI_HOST} exit; then
        echo -e "${RED}SSH connection failed. Please check your credentials and try again.${NC}"
        exit 1
    fi
    echo -e "${GREEN}SSH connection verified!${NC}"
}

# Main deployment process
echo -e "${GREEN}Starting deployment to ${PI_HOST}...${NC}"

# Verify SSH connection first
verify_ssh

# Check RPi OS version and architecture
echo -e "${YELLOW}Checking Raspberry Pi OS compatibility...${NC}"
ssh ${PI_USER}@${PI_HOST} "
    if ! grep -q 'Debian GNU/Linux 12' /etc/os-release; then
        echo '${RED}Error: This script requires Raspberry Pi OS Bookworm (Debian 12)${NC}'
        exit 1
    fi
    if [ \$(uname -m) != 'aarch64' ]; then
        echo '${RED}Error: This script requires 64-bit ARM architecture${NC}'
        exit 1
    fi
"
check_status "System compatibility check"

# Check USB drive status
echo -e "${YELLOW}Checking USB drive status...${NC}"
if ! df -h | grep -q "/Volumes/POS_DATA"; then
    echo -e "${RED}Error: USB drive not mounted at /Volumes/POS_DATA${NC}"
    echo -e "${YELLOW}Please run ./scripts/format_usb_mac.sh first${NC}"
    exit 1
fi
check_status "USB drive mount check"

# Verify USB drive contents
echo -e "${YELLOW}Verifying USB drive contents...${NC}"
if [ ! -d "/Volumes/POS_DATA/project_backup" ] || \
   [ ! -d "/Volumes/POS_DATA/pos_data" ] || \
   [ ! -d "/Volumes/POS_DATA/backups" ]; then
    echo -e "${RED}Error: USB drive is missing required directories${NC}"
    echo -e "${YELLOW}Please run ./scripts/format_usb_mac.sh first${NC}"
    exit 1
fi
check_status "USB drive verification"

# Step 1: Update Pi and reboot
echo -e "${YELLOW}Step 1: Updating Raspberry Pi...${NC}"
ssh ${PI_USER}@${PI_HOST} "sudo apt update && sudo apt upgrade -y && sudo reboot"

# Wait for Pi to reboot
echo -e "${YELLOW}Waiting for Pi to reboot...${NC}"
sleep 30
check_pi_connection

# Step 2: Copy project to USB drive
echo -e "${YELLOW}Step 2: Creating project backup on USB drive...${NC}"
cd "${PROJECT_DIR}"
echo -e "${YELLOW}Copying project files to USB drive...${NC}"
rsync -av --exclude 'venv' --exclude '__pycache__' --exclude '*.pyc' \
    --exclude '.git' --exclude '.DS_Store' --exclude 'data' \
    --exclude 'logs/*' --exclude '*.sqlite' \
    ./ "/Volumes/POS_DATA/project_backup/"
check_status "Project backup"

# Step 3: Set up USB drive on RPi4
echo -e "${YELLOW}Step 3: Setting up USB drive on RPi4...${NC}"

# Transfer setup script
echo -e "${YELLOW}Transferring setup script...${NC}"
scp scripts/setup_rpi.sh ${PI_USER}@${PI_HOST}:/home/${PI_USER}/
ssh ${PI_USER}@${PI_HOST} "chmod +x /home/${PI_USER}/setup_rpi.sh"

# Run setup script and wait for completion
echo -e "${YELLOW}Running USB setup script...${NC}"
echo -e "${RED}Please plug the USB drive into the RPi4 when prompted...${NC}"
ssh -t ${PI_USER}@${PI_HOST} "/home/${PI_USER}/setup_rpi.sh"

# Copy project files from USB backup
echo -e "${YELLOW}Setting up project from USB backup...${NC}"
ssh ${PI_USER}@${PI_HOST} "mkdir -p ${REMOTE_DIR} && \
    cp -r /media/usbdrive/project_backup/* ${REMOTE_DIR}/ && \
    chmod +x ${REMOTE_DIR}/scripts/*.sh && \
    cd ${REMOTE_DIR} && bash scripts/install_on_pi.sh"

# Final system verification
echo -e "${YELLOW}Performing final system verification...${NC}"
echo -e "${YELLOW}Waiting 30 seconds for services to stabilize...${NC}"
sleep 30

# Trigger reboot
echo -e "${YELLOW}Performing final reboot...${NC}"
ssh ${PI_USER}@${PI_HOST} "sudo reboot"

# Wait for reboot
echo -e "${YELLOW}Waiting for final reboot to complete...${NC}"
sleep 30
check_pi_connection

# Check service status and logs
echo -e "${YELLOW}Verifying system status...${NC}"
ssh ${PI_USER}@${PI_HOST} "echo -e '${GREEN}System Logs:${NC}' && \
    sudo journalctl -u pos-backend -n 50 --no-pager && \
    echo -e '\n${GREEN}Service Status:${NC}' && \
    sudo systemctl status pos-backend --no-pager"

echo -e "${GREEN}Deployment complete!${NC}"
echo -e "\nSystem is ready for frontend connections:"
echo -e "${GREEN}✓ USB drive mounted and configured${NC}"
echo -e "${GREEN}✓ Project files deployed${NC}"
echo -e "${GREEN}✓ Services running${NC}"
echo -e "\nAPI available at: http://pos.local:8000"
echo -e "API docs at: http://pos.local:8000/docs"
