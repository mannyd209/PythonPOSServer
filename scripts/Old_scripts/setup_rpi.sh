#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Error handling
set -e
trap 'echo -e "${RED}An error occurred. Setup failed.${NC}"; exit 1' ERR

# Function to check command status
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $1 successful${NC}"
    else
        echo -e "${RED}✗ $1 failed${NC}"
        exit 1
    fi
}

echo -e "${GREEN}Starting RPi4 setup...${NC}"

# Create mount point
echo -e "${YELLOW}Creating USB mount point...${NC}"
sudo mkdir -p /media/usbdrive
sudo chown -R pos:pos /media/usbdrive
check_status "Mount point creation"

# Wait for USB drive
echo -e "${YELLOW}Waiting for USB drive to be connected...${NC}"
echo -e "${RED}Please plug in your USB drive now...${NC}"

# Wait for the USB drive to appear
while true; do
    if lsblk | grep -q "sd"; then
        USB_DEVICE=$(lsblk | grep "sd" | head -n1 | awk '{print $1}')
        echo -e "${GREEN}Found USB drive: /dev/${USB_DEVICE}${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

# Get the exact partition
USB_PARTITION=$(lsblk -l | grep "^${USB_DEVICE}" | grep "part" | head -n1 | awk '{print $1}')
echo -e "${GREEN}Using partition: /dev/${USB_PARTITION}${NC}"

# Configure fstab
echo -e "${YELLOW}Configuring auto-mount...${NC}"

# Get user and group IDs
POS_UID=$(id -u pos)
POS_GID=$(id -g pos)

# Create fstab entry
FSTAB_ENTRY="/dev/${USB_PARTITION} /media/usbdrive exfat uid=${POS_UID},gid=${POS_GID},umask=000,nofail 0 0"

# Remove any existing USB mount entries
sudo sed -i '/\/media\/usbdrive/d' /etc/fstab

# Add new entry
echo "${FSTAB_ENTRY}" | sudo tee -a /etc/fstab
check_status "Fstab configuration"

# Reload systemd first
echo -e "${YELLOW}Reloading systemd...${NC}"
sudo systemctl daemon-reload
check_status "Systemd reload"

# Unmount if already mounted
echo -e "${YELLOW}Preparing mount point...${NC}"
if mountpoint -q /media/usbdrive; then
    sudo umount /media/usbdrive
fi

# Mount with new configuration
echo -e "${YELLOW}Mounting USB drive...${NC}"
sudo mount -a
check_status "Drive mounting"

# Verify mount
if ! mountpoint -q /media/usbdrive; then
    echo -e "${RED}Error: Drive not mounted properly${NC}"
    exit 1
fi

# Clean up macOS metadata files
echo -e "${YELLOW}Cleaning up macOS metadata...${NC}"
sudo rm -rf /media/usbdrive/.Spotlight-V100 2>/dev/null || true
sudo rm -rf /media/usbdrive/.fseventsd 2>/dev/null || true
sudo rm -rf /media/usbdrive/.Trashes 2>/dev/null || true
sudo find /media/usbdrive -name "._*" -delete 2>/dev/null || true
sudo find /media/usbdrive -name ".DS_Store" -delete 2>/dev/null || true
check_status "Cleanup"

# Create directories if they don't exist
echo -e "${YELLOW}Verifying directory structure...${NC}"
sudo mkdir -p /media/usbdrive/pos_data
sudo mkdir -p /media/usbdrive/backups
sudo mkdir -p /media/usbdrive/project_backup
sudo chown -R pos:pos /media/usbdrive/pos_data
sudo chown -R pos:pos /media/usbdrive/backups
sudo chown -R pos:pos /media/usbdrive/project_backup
check_status "Directory setup"

# Verify write access
echo -e "${YELLOW}Verifying write access...${NC}"
if touch /media/usbdrive/pos_data/.write_test && \
   touch /media/usbdrive/backups/.write_test; then
    rm /media/usbdrive/pos_data/.write_test
    rm /media/usbdrive/backups/.write_test
    echo -e "${GREEN}✓ Write access verified${NC}"
else
    echo -e "${RED}Error: Write access test failed${NC}"
    exit 1
fi

echo -e "${GREEN}RPi4 setup completed successfully!${NC}"
echo -e "\nUSB drive is mounted at: /media/usbdrive"
echo -e "Directories created:"
ls -la /media/usbdrive
echo -e "\nYou can now run deploy_to_pi.sh from your Mac"
