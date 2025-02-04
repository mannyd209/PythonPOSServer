#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Backup directory
BACKUP_DIR="/home/pi/AppPOS/backups"
DB_PATH="/media/usbdrive/pos_db.sqlite"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

# Check if database exists
if [ ! -f "${DB_PATH}" ]; then
    echo -e "${RED}Database file not found at ${DB_PATH}${NC}"
    exit 1
fi

# Create backup
echo -e "${YELLOW}Creating backup...${NC}"
cp "${DB_PATH}" "${BACKUP_DIR}/pos_db_${TIMESTAMP}.sqlite"

# Compress backup
echo -e "${YELLOW}Compressing backup...${NC}"
gzip "${BACKUP_DIR}/pos_db_${TIMESTAMP}.sqlite"

# Keep only last 7 backups
echo -e "${YELLOW}Cleaning old backups...${NC}"
ls -t "${BACKUP_DIR}"/pos_db_*.sqlite.gz | tail -n +8 | xargs -r rm

echo -e "${GREEN}Backup completed: ${BACKUP_DIR}/pos_db_${TIMESTAMP}.sqlite.gz${NC}"

# Show backup size
BACKUP_SIZE=$(du -h "${BACKUP_DIR}/pos_db_${TIMESTAMP}.sqlite.gz" | cut -f1)
echo -e "Backup size: ${YELLOW}${BACKUP_SIZE}${NC}"

# List all backups
echo -e "\nAvailable backups:"
ls -lh "${BACKUP_DIR}"/pos_db_*.sqlite.gz 