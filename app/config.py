"""
Application configuration module.

This module handles all configuration settings for the webhook client,
including logging setup and Kubernetes configuration management.
"""
import logging
import os
from typing import Optional


class ConfigurationError(Exception):
    """Raised when there's an error in configuration."""
    pass


class HealthzFilter(logging.Filter):
    """Filter to exclude /healthz endpoint logs."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out log records containing '/healthz' requests."""
        return record.getMessage().find("/healthz") == -1


class LoggingConfig:
    """Manages logging configuration."""
    
    @staticmethod
    def setup_logger(name: str = "webhook_client") -> logging.Logger:
        """
        Set up a logger with appropriate formatting and level.
        
        Args:
            name: Name of the logger
            
        Returns:
            Configured logger instance
        """
        logger = logging.getLogger(name)
        
        # Get log level from environment variable, default to INFO
        log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
        log_level = getattr(logging, log_level_name, logging.INFO)
        logger.setLevel(log_level)
        
        # Avoid adding multiple handlers if reloaded
        if not logger.handlers:
            handler = logging.StreamHandler()  # Log to stdout/stderr
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger


class AppConfig:
    """Application configuration container."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        
        # Network configuration
        self.switch_host = os.environ.get("SWITCH_HOST")
        self.switch_username = os.environ.get("SWITCH_USERNAME")
        self.switch_password = os.environ.get("SWITCH_PASSWORD")
        
        # Security configuration
        self.webhook_secret = os.environ.get("WEBHOOK_SECRET")
        
        # Server configuration
        self.port = int(os.environ.get("PORT", "8080"))
        
        # Notification configuration
        self.notification_endpoint = os.environ.get("NOTIFICATION_ENDPOINT")
        self.notification_timeout = int(os.environ.get("NOTIFICATION_TIMEOUT", "30"))  # 30 seconds
        
        # Webhook log configuration
        self.webhook_log_endpoint = os.environ.get("WEBHOOK_LOG_ENDPOINT")
        self.webhook_log_timeout = int(os.environ.get("WEBHOOK_LOG_TIMEOUT", "30"))  # 30 seconds
        
        # Logging configuration
        self.disable_healthz_logs = os.environ.get("DISABLE_HEALTHZ_LOGS", "true").lower() == "true"
        
        # Validate required configuration
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate configuration values."""
        if not self.webhook_secret:
            logger.warning("WEBHOOK_SECRET not configured. Signature verification will be skipped.")
        
        if not self.notification_endpoint:
            logger.warning("NOTIFICATION_ENDPOINT not configured. Notifications will be skipped.")
        
        if not self.webhook_log_endpoint:
            logger.warning("WEBHOOK_LOG_ENDPOINT not configured. Webhook logging will be skipped.")


# Initialize configuration
logger = LoggingConfig.setup_logger("switch_port_webhook_client")
config = AppConfig()

# Configure uvicorn access logger to filter out healthz requests if enabled
if config.disable_healthz_logs:
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.addFilter(HealthzFilter())

# Export commonly used configuration values for backward compatibility
WEBHOOK_SECRET = config.webhook_secret
PORT = config.port
SWITCH_HOST = config.switch_host
SWITCH_USERNAME = config.switch_username
SWITCH_PASSWORD = config.switch_password
DISABLE_HEALTHZ_LOGS = config.disable_healthz_logs
NOTIFICATION_ENDPOINT = config.notification_endpoint
NOTIFICATION_TIMEOUT = config.notification_timeout
WEBHOOK_LOG_ENDPOINT = config.webhook_log_endpoint
WEBHOOK_LOG_TIMEOUT = config.webhook_log_timeout
