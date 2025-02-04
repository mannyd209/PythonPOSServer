import subprocess
import logging
from typing import Optional
import requests
import time

logger = logging.getLogger(__name__)

class NetworkManager:
    def __init__(self):
        self.internet_enabled = False
        self._square_endpoints = [
            "connect.squareup.com",
            "*.squareup.com",
            "*.squarecdn.com"
        ]
    
    def _modify_firewall(self, allow: bool):
        """Modify firewall rules to allow/block internet access"""
        try:
            if allow:
                # Allow access only to Square endpoints
                for endpoint in self._square_endpoints:
                    subprocess.run([
                        'sudo', 'iptables', '-A', 'OUTPUT', 
                        '-p', 'tcp', 
                        '-d', endpoint, 
                        '--dport', '443', 
                        '-j', 'ACCEPT'
                    ], check=True)
            else:
                # Block all outgoing internet traffic except local network
                subprocess.run([
                    'sudo', 'iptables', '-A', 'OUTPUT',
                    '-d', '192.168.0.0/16',  # Local network
                    '-j', 'ACCEPT'
                ], check=True)
                subprocess.run([
                    'sudo', 'iptables', '-A', 'OUTPUT',
                    '-d', '127.0.0.0/8',     # Localhost
                    '-j', 'ACCEPT'
                ], check=True)
                subprocess.run([
                    'sudo', 'iptables', '-A', 'OUTPUT',
                    '-j', 'DROP'             # Drop all other traffic
                ], check=True)
            
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to modify firewall: {e}")
            return False
    
    async def enable_internet(self) -> bool:
        """Enable internet access for Square transactions"""
        if not self.internet_enabled:
            if self._modify_firewall(True):
                self.internet_enabled = True
                logger.info("Internet access enabled for Square transactions")
                return True
        return False
    
    async def disable_internet(self) -> bool:
        """Disable internet access after transaction"""
        if self.internet_enabled:
            if self._modify_firewall(False):
                self.internet_enabled = False
                logger.info("Internet access disabled")
                return True
        return False
    
    async def check_square_connection(self) -> bool:
        """Check if Square endpoints are accessible"""
        try:
            response = requests.get(
                "https://connect.squareup.com/health", 
                timeout=5
            )
            return response.status_code == 200
        except:
            return False

# Global network manager instance
network_manager = NetworkManager() 