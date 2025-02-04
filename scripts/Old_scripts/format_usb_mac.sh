#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Error handling
set -e
trap 'echo -e "${RED}An error occurred. USB formatting failed.${NC}"; exit 1' ERR

# Function to check command status
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $1 successful${NC}"
    else
        echo -e "${RED}✗ $1 failed${NC}"
        exit 1
    fi
}

echo -e "${GREEN}Starting USB drive formatting for RPi4 deployment...${NC}"

# List available disks
diskutil list

# Ask for disk identifier
echo -e "${YELLOW}Enter the disk identifier for your USB drive (e.g., disk2):${NC}"
read DISK_ID

# Verify disk selection
echo -e "${RED}WARNING: This will erase all data on /dev/${DISK_ID}${NC}"
echo -e "${YELLOW}Please verify this is the correct disk.${NC}"
echo -e "Type 'yes' to continue:"
read CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${RED}Aborting.${NC}"
    exit 1
fi

# Unmount disk
echo -e "${YELLOW}Unmounting disk...${NC}"
diskutil unmountDisk /dev/${DISK_ID}
check_status "Disk unmount"

# Format disk as ExFAT with MBR
echo -e "${YELLOW}Formatting disk as ExFAT...${NC}"
diskutil eraseDisk ExFAT "POS_DATA" MBR /dev/${DISK_ID}
check_status "Disk formatting"

# Wait for the disk to be available
sleep 3

# Mount the disk
echo -e "${YELLOW}Mounting disk...${NC}"
diskutil mountDisk /dev/${DISK_ID}
sleep 2

# Verify mount
if [ ! -d "/Volumes/POS_DATA" ]; then
    echo -e "${RED}Error: Drive not mounted at /Volumes/POS_DATA${NC}"
    exit 1
fi

# Create directory structure
echo -e "${YELLOW}Creating directory structure...${NC}"
mkdir -p "/Volumes/POS_DATA/pos_data"
mkdir -p "/Volumes/POS_DATA/backups"
mkdir -p "/Volumes/POS_DATA/project_backup"
check_status "Directory creation"

# Basic system service configuration
echo -e "${YELLOW}Configuring system services...${NC}"
mdutil -i off "/Volumes/POS_DATA" 2>/dev/null || true

# Set up permissions
echo -e "${YELLOW}Setting up permissions...${NC}"
chmod -R 777 "/Volumes/POS_DATA/pos_data"
chmod -R 777 "/Volumes/POS_DATA/backups"
chmod -R 777 "/Volumes/POS_DATA/project_backup"
touch "/Volumes/POS_DATA/.metadata_never_index" 2>/dev/null || true
check_status "Permission setup"

# Copy project files to USB drive
echo -e "${YELLOW}Creating project backup on USB drive...${NC}"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
rsync -av --exclude 'venv' --exclude '__pycache__' --exclude '*.pyc' \
    --exclude '.git' --exclude '.DS_Store' --exclude 'data' \
    --exclude 'logs/*' --exclude '*.sqlite' \
    "${PROJECT_DIR}/" "/Volumes/POS_DATA/project_backup/"
check_status "Project backup"

echo -e "${GREEN}USB drive formatted and prepared successfully!${NC}"
echo -e "\nDrive is now ready for RPi4 deployment."
echo -e "Mount point: /Volumes/POS_DATA"
echo -e "\nDirectory structure:"
echo -e "${GREEN}✓ /Volumes/POS_DATA/pos_data (777)${NC}"
echo -e "${GREEN}✓ /Volumes/POS_DATA/backups (777)${NC}"
echo -e "${GREEN}✓ /Volumes/POS_DATA/project_backup (777)${NC}"

echo -e "\n${YELLOW}Project files have been backed up to the USB drive.${NC}"
echo -e "${YELLOW}You can now proceed with deployment.${NC}"
