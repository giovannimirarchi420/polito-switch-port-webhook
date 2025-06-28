"""
Configuration management for the switch port webhook.

This module handles environment variable loading and application configuration.
"""
import os
import logging
from typing import Optional

class AppConfig:
    """Application configuration from environment variables."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        # Server configuration
        self.port = int(os.environ.get("PORT", "5002"))
        self.log_level = os.environ.get("LOG_LEVEL", "INFO")
        
        # Switch configuration
        self.switch_host = os.environ.get("SWITCH_HOST", "192.168.24.67")
        self.switch_username = os.environ.get("SWITCH_USERNAME", "admin")
        self.switch_password = os.environ.get("SWITCH_PASSWORD", "admin")
        self.switch_device_type = os.environ.get("SWITCH_DEVICE_TYPE", "cisco_ios")
        self.switch_port = int(os.environ.get("SWITCH_PORT", "22"))
        self.switch_timeout = int(os.environ.get("SWITCH_TIMEOUT", "30"))
        
        # VLAN configuration
        self.default_vlan_id = int(os.environ.get("DEFAULT_VLAN_ID", "10"))
        
        # Security configuration
        self.webhook_secret = os.environ.get("WEBHOOK_SECRET")
        
        # Notification configuration
        self.notification_endpoint = os.environ.get("NOTIFICATION_ENDPOINT")
        self.notification_timeout = int(os.environ.get("NOTIFICATION_TIMEOUT", "30"))
        self.webhook_log_endpoint = os.environ.get("WEBHOOK_LOG_ENDPOINT")
        self.webhook_log_timeout = int(os.environ.get("WEBHOOK_LOG_TIMEOUT", "30"))
    
    @property
    def is_webhook_security_enabled(self) -> bool:
        """Check if webhook signature verification is enabled."""
        return bool(self.webhook_secret)

# Global configuration instance
config = AppConfig()

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Export commonly used values
PORT = config.port
SWITCH_HOST = config.switch_host
SWITCH_USERNAME = config.switch_username
SWITCH_PASSWORD = config.switch_password
SWITCH_DEVICE_TYPE = config.switch_device_type
SWITCH_PORT = config.switch_port
SWITCH_TIMEOUT = config.switch_timeout
DEFAULT_VLAN_ID = config.default_vlan_id
WEBHOOK_SECRET = config.webhook_secret
NOTIFICATION_ENDPOINT = config.notification_endpoint
NOTIFICATION_TIMEOUT = config.notification_timeout
WEBHOOK_LOG_ENDPOINT = config.webhook_log_endpoint
WEBHOOK_LOG_TIMEOUT = config.webhook_log_timeout
