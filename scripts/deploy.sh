#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Error handling
set -e
trap 'echo -e "${RED}An error occurred. Deployment failed.${NC}"; exit 1' ERR

# Set environment variables
PI_HOST="pos.local"
PI_HOSTNAME="pos"
PI_USER="pos"
PROJECT_DIR="/Volumes/MacSSD/AppPOS"
REMOTE_DIR="/home/${PI_USER}/AppPOS"
LOG_FILE="$HOME/deploy.log"

# Ensure log file exists
touch $LOG_FILE
chmod 644 $LOG_FILE

# SSH options
SSH_OPTS="-o ServerAliveInterval=60 -o ServerAliveCountMax=10 -o ConnectTimeout=30 -o StrictHostKeyChecking=accept-new"

# Log function
echo_log() {
    local message="$1"
    echo -e "[$(date)] $message" | tee -a $LOG_FILE
}

# Function to check Pi connection
check_pi_connection() {
    local max_attempts=30
    local attempt=1
    
    echo_log "Waiting for Pi to become accessible..."
    while [ $attempt -le $max_attempts ]; do
        if ping -c 1 $PI_HOST >/dev/null 2>&1; then
            echo_log "Pi is accessible!"
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo_log "Failed to connect to Pi after $max_attempts attempts"
    exit 1
}

# Function to setup SSH key
setup_ssh_key() {
    echo_log "Setting up SSH key authentication..."
    if [ ! -f "$HOME/.ssh/id_rsa" ]; then
        ssh-keygen -t rsa -N "" -f "$HOME/.ssh/id_rsa"
    fi
    ssh-copy-id -o ConnectTimeout=30 -o StrictHostKeyChecking=accept-new ${PI_USER}@${PI_HOST} || echo_log "SSH key already exists on Pi"
}

# Function to clean previous installation
cleanup_previous_installation() {
    echo_log "Cleaning up previous installation on Raspberry Pi..."
    ssh ${SSH_OPTS} ${PI_USER}@${PI_HOST} "
        sudo rm -rf ${REMOTE_DIR}
        sudo mkdir -p ${REMOTE_DIR}
    "
}

# Function to setup Raspberry Pi environment
setup_pi_environment() {
    echo_log "Setting up Raspberry Pi environment..."
    ssh ${SSH_OPTS} ${PI_USER}@${PI_HOST} "
        ARCH=\$(uname -m) || ARCH='UNKNOWN'
        echo 'Detected architecture: ' \$ARCH | tee -a \$HOME/deploy.log
        if [ \"\$ARCH\" != 'aarch64' ] && [ \"\$ARCH\" != 'arm64' ]; then
            echo 'Warning: Detected non-64-bit architecture (\$ARCH). Proceeding with caution.'
        fi
        sudo apt update && sudo apt install -y exfatprogs exfat-fuse python3-venv libsqlite3-dev
    "
}

# Function to format, mount, and prepare USB drive
setup_usb_drive() {
    echo_log "Setting up USB drive..."

    # Identify the largest partition on the USB drive
    USB_DISK=$(lsblk -o NAME,SIZE,TYPE,MOUNTPOINT | grep -E 'sd[a-z][0-9]+' | sort -k2 -hr | head -n 1 | awk '{print "/dev/" $1}')

    if [ -z "$USB_DISK" ]; then
        echo_log "No USB drive found. Exiting..."
        exit 1
    fi

    echo_log "USB partition selected: $USB_DISK"

    # Ensure the drive is not already mounted
    if mount | grep -q "/media/usbdrive"; then
        echo_log "USB drive is already mounted."
    else
        echo_log "Formatting the USB drive..."
        sudo mkfs.ext4 -F $USB_DISK

        echo_log "Creating mount point..."
        sudo mkdir -p /media/usbdrive

        echo_log "Mounting USB drive..."
        sudo mount $USB_DISK /media/usbdrive

        echo_log "Setting up fstab entry for persistence..."
        UUID=$(blkid -s UUID -o value $USB_DISK)
        echo "UUID=$UUID /media/usbdrive ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab

        echo_log "USB drive mounted successfully."
    fi

    # Ensure proper directories exist on the USB drive
    echo_log "Creating required directories on the USB drive..."
    sudo mkdir -p /media/usbdrive/project_backup
    sudo mkdir -p /media/usbdrive/pos_data
    sudo mkdir -p /media/usbdrive/backups

    # Set appropriate permissions
    sudo chown -R ${PI_USER}:${PI_USER} /media/usbdrive
    sudo chmod -R 755 /media/usbdrive

    echo_log "USB drive setup complete."
}

# Function to transfer project files
transfer_project() {
    echo_log "Transferring project files to Raspberry Pi..."
    ssh ${SSH_OPTS} ${PI_USER}@${PI_HOST} "sudo chown -R ${PI_USER}:${PI_USER} ${REMOTE_DIR} && sudo chmod -R 755 ${REMOTE_DIR}" 
    rsync -avz --exclude '.git' --exclude '__pycache__' -e "ssh ${SSH_OPTS}" ./ ${PI_USER}@${PI_HOST}:${REMOTE_DIR}/
}

# Function to setup database
setup_database() {
    echo_log "Running database setup on Raspberry Pi..."
    ssh ${SSH_OPTS} ${PI_USER}@${PI_HOST} "
        cd ${REMOTE_DIR}/scripts
        python3 -m venv ${REMOTE_DIR}/venv
        source ${REMOTE_DIR}/venv/bin/activate
        if [ -f ${REMOTE_DIR}/requirements.txt ]; then
            pip install --upgrade pip
            pip install --upgrade pip && pip install -r ${REMOTE_DIR}/requirements.txt && pip install uvicorn
        fi
        PYTHONPATH=${REMOTE_DIR} python3 ${REMOTE_DIR}/scripts/setup_database.py | tee -a \$HOME/deploy.log
    "
}

# Function to install and start POS backend service
install_and_start_pos_backend() {
    echo_log "Installing and starting POS backend service..."
    ssh ${SSH_OPTS} ${PI_USER}@${PI_HOST} "
        sudo cp ${REMOTE_DIR}/scripts/pos-backend.service /etc/systemd/system/pos-backend.service
        sudo systemctl daemon-reload
        sudo systemctl enable pos-backend
        sudo systemctl restart pos-backend
        echo 'POS backend service restarted.' | tee -a \$HOME/deploy.log
    "
    
    echo_log "Checking POS backend service status..."
    ssh ${SSH_OPTS} ${PI_USER}@${PI_HOST} "
        systemctl status pos-backend --no-pager
    "
}

# Function to check server status
check_server_status() {
    echo_log "Checking API health status..."
    ssh ${SSH_OPTS} ${PI_USER}@${PI_HOST} "
        curl -s http://localhost:8000/health | tee -a \$HOME/deploy.log
    "
}

# Main deployment flow
echo_log "Starting deployment process..."
check_pi_connection
setup_ssh_key
cleanup_previous_installation
setup_pi_environment
setup_usb_drive  # Added to setup USB drive before transferring project files
transfer_project
setup_database
install_and_start_pos_backend
check_server_status
echo_log "Deployment complete!"
