# Restaurant POS System

## Overview
This is a Restaurant POS system designed to run on a Raspberry Pi 4. The system provides a complete point-of-sale solution with staff management, order processing, and payment integration capabilities.

## System Requirements
- Raspberry Pi 4
- Raspberry Pi OS 64-bit lite
- Network connection

## System Configuration
- Hostname: pos
- Username: pos
- IP Address: *.*.*.* (will be provided during setup)

## Pre-deployment Steps

1. Prepare the Raspberry Pi:
- Install Raspberry Pi OS 64-bit lite on the SD card
- Set hostname to 'pos' during initial setup
- Create user named 'pos' during initial setup
- Connect to your network

## Deployment

1. Deploy to Raspberry Pi:
```bash
# Deploy the project
./scripts/deploy.sh
```

This will:
- Update the Raspberry Pi system
- Transfer all project files
- Install dependencies
- Configure services
- Start the POS backend service

## Post-deployment Verification

1. Check Service Status:
```bash
# SSH into your Pi
ssh pos@*.*.*.*

# Check service status
sudo systemctl status pos-backend
```

2. Verify API Access:
- Open http://*.*.*.*:8000/docs in a browser
- You should see the Swagger UI documentation

## Directory Structure

- `/home/pos/AppPOS/` - Application files
- `/home/pos/AppPOS/data/` - Database files
- `/home/pos/AppPOS/migrations/` - Database migrations

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

2. If database access fails:
```bash
# Check permissions
sudo chown -R pos:pos /home/pos/AppPOS/data
```

3. If experiencing performance issues:
```bash
# Check CPU governor status
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

## Security Notes

- The system uses PIN-based authentication for staff
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
