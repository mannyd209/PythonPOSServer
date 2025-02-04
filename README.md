# Restaurant POS System - RPi4 Deployment Guide

## Overview
This is a Restaurant POS system designed to run on a Raspberry Pi 4. The system uses the RPi4's SD card for the operating system and server, while storing all data on an external USB drive for improved reliability and performance.

## System Requirements
- Raspberry Pi 4
- Raspberry Pi OS 64-bit lite
- USB 3.0 flash drive (400mbps capable)
- Network connection

## System Configuration
- Hostname: pos
- Username: pos
- IP Address: 192.168.1.248

## Pre-deployment Steps (on Mac)

1. Format the USB Drive:
```bash
# Run the formatting script
./scripts/format_usb_mac.sh
```
This will:
- Format the USB drive as ExFAT
- Create necessary directories for data and backups
- Prepare the drive for RPi4 use

2. Prepare the Raspberry Pi:
- Install Raspberry Pi OS 64-bit lite on the SD card
- Set hostname to 'pos' during initial setup
- Create user named 'pos' during initial setup
- Connect to your network

## Deployment Steps

1. Deploy to Raspberry Pi:
```bash
# Deploy the project (pre-configured for pos@192.168.1.248)
./scripts/deploy_to_pi.sh
```
This will:
- Update the Raspberry Pi system
- Transfer all project files
- Transfer USB drive data
- Install dependencies
- Configure services
- Set up auto-mounting of USB drive
- Start the POS backend service

## Post-deployment Verification

1. Check Service Status:
```bash
# SSH into your Pi
ssh pos@192.168.1.248

# Check service status
sudo systemctl status pos-backend
```

2. Verify API Access:
- Open http://192.168.1.248:8000/docs in a browser
- You should see the Swagger UI documentation

3. Check USB Drive:
```bash
# Verify USB drive is mounted
df -h /media/usbdrive

# Check database directory
ls -la /media/usbdrive/pos_data
```

## Directory Structure

- `/media/usbdrive/pos_data/` - Database files
- `/media/usbdrive/backups/` - Backup files
- `/home/pos/AppPOS/` - Application files

## Performance Optimizations

The deployment includes optimizations specific to RPi4 64-bit lite with USB 3.0:

### USB 3.0 Optimizations
- Disabled USB power management for maximum throughput
- Optimized kernel parameters for USB storage
- Configured rsync with USB 3.0 specific flags (--compress-level=0 --whole-file)
- Tuned system parameters for 400mbps throughput
- Optimized buffer sizes for better performance

### RPi4 64-bit lite Optimizations
- Minimal GPU memory (16MB) for headless operation
- Performance CPU governor enabled
- Multi-worker uvicorn configuration
- Optimized memory management for database operations
- uvloop and httptools for enhanced performance

### Database Optimizations
- Configured SQLite for USB 3.0 storage
- Optimized write patterns for flash storage
- Tuned cache settings for better performance
- Configured backup strategies for USB storage

## Maintenance

### Backup Database:
```bash
# Run backup script
./scripts/backup_db.sh
```

### Update System:
```bash
# Update packages and restart services
./scripts/manage_server.sh update
```

### View Logs:
```bash
# View backend service logs
journalctl -u pos-backend -f
```

## Troubleshooting

1. If service fails to start:
```bash
# Check logs
sudo journalctl -u pos-backend -n 50
```

2. If USB drive is not mounting:
```bash
# Check mount status
sudo systemctl status media-usbdrive.mount

# Check USB 3.0 status
lsusb -t

# Manually mount
sudo mount -a
```

3. If database access fails:
```bash
# Check permissions
sudo chown -R pos:pos /media/usbdrive

# Check USB performance
sudo hdparm -tT /dev/sda
```

4. If experiencing performance issues:
```bash
# Check CPU governor status
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Monitor USB throughput
iostat -x 1
```

## Security Notes

- The system uses PIN-based authentication for staff
- All sensitive data is stored on the USB drive
- Service runs under a dedicated 'pos' user
- Limited sudo permissions for service management
- Optimized for headless operation

## Support

For issues or questions:
1. Check the logs: `journalctl -u pos-backend -f`
2. Review documentation in the `Docs/` directory
3. Submit issues to the project repository

## License
MIT License - See LICENSE file for details
