#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Error handling
set -e
trap 'echo -e "${RED}An error occurred. USB setup failed.${NC}"; exit 1' ERR

# Function to check command status
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $1 successful${NC}"
    else
        echo -e "${RED}✗ $1 failed${NC}"
        exit 1
    fi
}

# Function to safely unmount all partitions of a device
safe_unmount() {
    local device=$1
    echo -e "${YELLOW}Unmounting all partitions of ${device}...${NC}"
    
    # Stop any services that might be using the drive
    sudo systemctl stop pos-backend || true
    sudo systemctl stop media-usbdrive.mount || true
    
    # Get all mounted partitions for the device
    local partitions=$(lsblk -l -o NAME,MOUNTPOINT | grep "^${device#/dev/}" | awk '$2 != "" {print $2}')
    
    # Unmount each partition
    for mount_point in $partitions; do
        echo -e "${YELLOW}Unmounting ${mount_point}...${NC}"
        # Kill any processes using the mount point
        sudo fuser -km "${mount_point}" 2>/dev/null || true
        sudo umount -f "${mount_point}" 2>/dev/null || true
    done
    
    # Additional cleanup: unmount by device name
    sudo umount -f "${device}"* 2>/dev/null || true
    
    # Wait a moment for system to process unmounting
    sleep 2
    
    # Verify nothing is mounted
    if mount | grep "${device}" > /dev/null; then
        echo -e "${RED}Warning: Some partitions could not be unmounted.${NC}"
        return 1
    fi
    
    return 0
}

# Check if this is phase 2 of the setup
if [ "$1" = "phase2" ]; then
    echo -e "${GREEN}Starting USB drive setup phase 2...${NC}"
    
    # Use sda2 specifically
    USB_DEVICE="/dev/sda2"
    
    # Check if the device exists
    if [ ! -b "$USB_DEVICE" ]; then
        echo -e "${RED}Error: ${USB_DEVICE} not found!${NC}"
        echo -e "${YELLOW}Please ensure USB drive is plugged into the correct port and try again.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Found USB drive at: ${USB_DEVICE}${NC}"
    
    # Create GPT partition table without confirmation
    sudo parted ${USB_DEVICE} --script mklabel gpt
    check_status "Partition table creation"
    
    # Create single partition without confirmation
    sudo parted ${USB_DEVICE} --script mkpart primary 0% 100%
    check_status "Partition creation"
    
    # Wait for the system to recognize the new partition
    echo -e "${YELLOW}Waiting for system to recognize new partition...${NC}"
    sleep 5
    
    # Format as exFAT without confirmation
    sudo mkfs.exfat -n "POS_DATA" ${USB_DEVICE}
    check_status "Drive formatting"
    
    # Get USB drive UUID
    USB_UUID=$(sudo blkid -s UUID -o value ${USB_DEVICE})
    if [ -z "$USB_UUID" ]; then
        echo -e "${RED}Failed to get USB drive UUID!${NC}"
        exit 1
    fi
    check_status "UUID retrieval"
    
    # Create mount unit
    echo -e "${YELLOW}Creating mount unit...${NC}"
    cat << EOF | sudo tee /etc/systemd/system/media-usbdrive.mount
[Unit]
Description=USB Drive Mount for POS Database
DefaultDependencies=no
After=systemd-udev-settle.service
Before=umount.target
Conflicts=umount.target

[Mount]
What=UUID=${USB_UUID}
Where=/media/usbdrive
Type=exfat
Options=uid=pos,gid=pos,rw,user,exec,umask=000,nofail
TimeoutSec=30

[Install]
WantedBy=multi-user.target
EOF
    check_status "Mount unit creation"

    # Create backend service with better dependency handling
    echo -e "${YELLOW}Creating backend service...${NC}"
    cat << EOF | sudo tee /etc/systemd/system/pos-backend.service
[Unit]
Description=Restaurant POS Backend Service
After=network.target media-usbdrive.mount
Wants=media-usbdrive.mount
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

# Wait for mount and create directories
ExecStartPre=/bin/bash -c 'while ! mountpoint -q /media/usbdrive; do echo "Waiting for USB drive mount..."; sleep 2; done'
ExecStartPre=/bin/bash -c 'mkdir -p /media/usbdrive/pos_data /media/usbdrive/backups && chown -R pos:pos /media/usbdrive/pos_data /media/usbdrive/backups'

# Initialize database if it doesn't exist
ExecStartPre=/bin/bash -c 'cd /home/pos/AppPOS && source venv/bin/activate && if [ ! -f /media/usbdrive/pos_data/pos_db.sqlite ]; then python -c "from models.base import Base, engine; Base.metadata.create_all(bind=engine)"; fi'

ExecStart=/home/pos/AppPOS/venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8000

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
    check_status "Service creation"

    # Create mount point and set permissions
    echo -e "${YELLOW}Setting up mount point...${NC}"
    sudo mkdir -p /media/usbdrive
    sudo chown pos:pos /media/usbdrive
    check_status "Mount point setup"

    # Reload systemd and restart services
    echo -e "${YELLOW}Reloading systemd and starting services...${NC}"
    sudo systemctl daemon-reload

    # Start and verify mount
    echo -e "${YELLOW}Starting USB mount...${NC}"
    sudo systemctl enable media-usbdrive.mount
    sudo systemctl start media-usbdrive.mount
    
    # Wait for mount to be active
    echo -e "${YELLOW}Waiting for USB mount to be active...${NC}"
    for i in {1..30}; do
        if mountpoint -q /media/usbdrive; then
            echo -e "${GREEN}USB drive mounted successfully${NC}"
            break
        fi
        if [ $i -eq 30 ]; then
            echo -e "${RED}Failed to mount USB drive${NC}"
            exit 1
        fi
        echo -n "."
        sleep 1
    done

    # Create directories and set permissions
    echo -e "${YELLOW}Creating data directories...${NC}"
    sudo mkdir -p /media/usbdrive/pos_data /media/usbdrive/backups
    sudo chown -R pos:pos /media/usbdrive/pos_data /media/usbdrive/backups
    check_status "Directory creation"

    # Start and verify backend service
    echo -e "${YELLOW}Starting POS backend service...${NC}"
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

    # Final verification
    echo -e "${YELLOW}Verifying setup...${NC}"
    if ! systemctl is-active --quiet pos-backend; then
        echo -e "${RED}POS backend service failed to start. Checking logs...${NC}"
        journalctl -u pos-backend --no-pager -n 50
        exit 1
    fi

    echo -e "${GREEN}USB drive setup complete!${NC}"
    echo -e "\nService Status:"
    systemctl status pos-backend --no-pager

    echo -e "\nUSB Drive Status:"
    df -h /media/usbdrive
    ls -la /media/usbdrive/pos_data/

    echo -e "\nAPI should be available at: http://$(hostname -I | awk '{print $1}'):8000"
    echo -e "Check the API documentation at: http://$(hostname -I | awk '{print $1}'):8000/docs"
    
else
    # Phase 1: Initial setup and partition table wiping
    echo -e "${GREEN}Starting USB drive setup phase 1...${NC}"
    
    # Use sda2 specifically
    USB_DEVICE="/dev/sda2"
    
    # Check if the device exists
    if [ ! -b "$USB_DEVICE" ]; then
        echo -e "${RED}Error: ${USB_DEVICE} not found!${NC}"
        echo -e "${YELLOW}Please ensure USB drive is plugged into the correct port and try again.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Found USB drive at: ${USB_DEVICE}${NC}"
    
    # Safely unmount all partitions
    if ! safe_unmount "${USB_DEVICE}"; then
        echo -e "${RED}Cannot safely proceed. Please ensure no processes are using the drive and try again.${NC}"
        exit 1
    fi
    
    # Wipe partition table
    echo -e "${YELLOW}Wiping existing partition table...${NC}"
    sudo dd if=/dev/zero of=${USB_DEVICE} bs=512 count=1 conv=notrunc
    sync
    sleep 2
    check_status "Partition table wiping"
    
    # Schedule phase 2 to run after reboot
    echo -e "${YELLOW}Setting up phase 2 to run after reboot...${NC}"
    (crontab -l 2>/dev/null | grep -v "setup_usb.sh phase2"; echo "@reboot sleep 30 && cd /home/pos/AppPOS && ./scripts/setup_usb.sh phase2") | crontab -
    
    echo -e "${GREEN}Phase 1 complete. System will reboot to apply partition table changes.${NC}"
    echo -e "${YELLOW}The setup will continue automatically after reboot.${NC}"
    sleep 5
    sudo reboot
fi 