"""
Utility functions for webhook payload processing.

This module provides helper functions for safely parsing and handling
custom parameters from webhook payloads, specifically for switch port configuration.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Union

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

from .config import logger
from . import config, models
from .services import security, switch, notification

# Constants for event types
EVENT_START = 'EVENT_START'
EVENT_END = 'EVENT_END'
EVENT_DELETED = 'EVENT_DELETED'


def parse_custom_parameters(custom_params_str: Optional[str]) -> Dict[str, Any]:
    """
    Safe parsing of custom parameters from webhook payload.
    
    Args:
        custom_params_str: JSON serialized string of custom parameters
        
    Returns:
        Dictionary with custom parameters or empty dict if not present/invalid
    """
    if not custom_params_str:
        return {}
    
    try:
        return json.loads(custom_params_str)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Error parsing customParameters: {e}")
        return {}


def get_custom_parameter(custom_params: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Get a specific custom parameter with default value.
    
    Args:
        custom_params: Dictionary of custom parameters
        key: Key of the parameter to get
        default: Default value if parameter doesn't exist
        
    Returns:
        Parameter value or default value
    """
    return custom_params.get(key, default)


def has_custom_parameters(custom_params_str: Optional[str]) -> bool:
    """
    Check if valid custom parameters are present.
    
    Args:
        custom_params_str: JSON serialized string of custom parameters
        
    Returns:
        True if valid custom parameters are present, False otherwise
    """
    if not custom_params_str:
        return False
    
    custom_params = parse_custom_parameters(custom_params_str)
    return bool(custom_params)


def get_vlan_name_from_custom_params(custom_params_str: Optional[str]) -> Optional[str]:
    """
    Extract vlan_name from custom parameters.
    
    Args:
        custom_params_str: JSON serialized string of custom parameters
        
    Returns:
        VLAN name if present, None otherwise
    """
    custom_params = parse_custom_parameters(custom_params_str)
    return get_custom_parameter(custom_params, "vlan_name")


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    Parse timestamp string to datetime object.
    
    Args:
        timestamp_str: ISO format timestamp string
        
    Returns:
        datetime object
        
    Raises:
        ValueError: If timestamp format is invalid
    """
    try:
        # Replace Z with timezone offset
        timestamp_str = timestamp_str.replace('Z', '+00:00')
        
        # Handle nanosecond precision by truncating to microseconds
        if '.' in timestamp_str:
            # Find the decimal point and truncate fractional seconds to 6 digits
            if '+' in timestamp_str:
                # Has timezone
                datetime_part, tz_part = timestamp_str.rsplit('+', 1)
                date_time, fractional = datetime_part.rsplit('.', 1)
                # Truncate fractional seconds to 6 digits (microseconds)
                fractional = fractional[:6].ljust(6, '0')
                timestamp_str = f"{date_time}.{fractional}+{tz_part}"
            else:
                # No explicit timezone
                date_time, fractional = timestamp_str.rsplit('.', 1)
                # Truncate fractional seconds to 6 digits (microseconds)
                fractional = fractional[:6].ljust(6, '0')
                timestamp_str = f"{date_time}.{fractional}"
            
        return datetime.fromisoformat(timestamp_str)
    except ValueError as e:
        logger.error(f"Failed to parse timestamp '{timestamp_str}': {e}")
        raise ValueError(f"Invalid timestamp format: {timestamp_str}")


async def verify_webhook_signature(request: Request, signature: Optional[str]) -> bytes:
    """
    Verify webhook signature and return raw payload.
    
    Args:
        request: FastAPI request object
        signature: Signature from webhook header
        
    Returns:
        Raw payload bytes
        
    Raises:
        HTTPException: If signature verification fails
    """
    raw_payload = await request.body()
    
    if config.WEBHOOK_SECRET:
        if not security.verify_signature(raw_payload, signature):
            logger.warning("Webhook signature verification failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
    
    return raw_payload


def create_success_response(action: str, resource_name: str, user_id: Optional[str]) -> JSONResponse:
    """Create a standardized success response for single event operations."""
    return JSONResponse({
        "status": "success",
        "message": f"Successfully {action}d switch port '{resource_name}'",
        "userId": user_id
    })


def handle_switch_port_start_event(
    payload: models.WebhookPayload
) -> bool:
    """
    Handle switch port reservation start event. Returns True on success.
    """
    resource_name = payload.resource_name
    custom_parameters = payload.custom_parameters
    webhook_id = payload.webhook_id
    user_id = payload.user_id or "unknown"
    event_id = payload.event_id
    username = payload.username
    resource_id = payload.resource_id

    try:
        # Extract VLAN name from custom parameters
        vlan_name = get_vlan_name_from_custom_params(custom_parameters)
        if not vlan_name:
            logger.error(f"No vlan_name found in custom parameters for switch port '{resource_name}'")
            return False
        
        # Use resource name directly as interface name
        interface_name = resource_name
        
        # Configure switch port with VLAN
        switch_manager = switch.get_switch_port_manager()
        success = switch_manager.configure_switch_port(interface_name, vlan_name, username)
        
        if success:
            logger.info(f"[{EVENT_START}] Successfully configured switch interface {interface_name} with VLAN '{vlan_name}' (Event ID: {event_id})")
            
            # Send success notification
            notification.send_switch_port_notification(
                webhook_id=webhook_id,
                user_id=user_id,
                resource_name=resource_name,
                success=True,
                event_id=event_id,
                resource_id=resource_id
            )
            
            # Send webhook log for successful configuration
            notification.send_webhook_log(
                webhook_id=webhook_id,
                event_type=EVENT_START,
                success=True,
                payload_data=json.dumps(payload.model_dump()),
                status_code=200,
                response=f"Switch port '{resource_name}' configured with VLAN '{vlan_name}'",
                retry_count=0,
                metadata={"resourceName": resource_name, "userId": user_id, "webhookId": webhook_id, "vlanName": vlan_name},
                resource_id=resource_id
            )
        else:
            logger.error(f"[{EVENT_START}] Failed to configure switch interface {interface_name} with VLAN '{vlan_name}' (Event ID: {event_id})")
            
            # Send failure notification
            notification.send_switch_port_notification(
                webhook_id=webhook_id,
                user_id=user_id,
                resource_name=resource_name,
                success=False,
                error_message=f"Failed to configure switch port with VLAN '{vlan_name}'",
                event_id=event_id,
                resource_id=resource_id
            )
        
        return success
        
    except Exception as e:
        logger.error(f"Error configuring switch port '{resource_name}': {str(e)}")
        
        # Send failure notification
        notification.send_switch_port_notification(
            webhook_id=event_id,
            user_id=user_id,
            resource_name=resource_name,
            success=False,
            error_message=str(e),
            event_id=event_id,
            resource_id=resource_id
        )
        
        return False


def handle_switch_port_end_event(
    payload: Union[models.WebhookPayload, models.EventWebhookPayload]
) -> bool:
    """
    Handle switch port reservation end event. Returns True on success.
    """
    if isinstance(payload, models.WebhookPayload):
        resource_name = payload.resource_name
        event_id = payload.event_id
        user_id = payload.user_id or "unknown"
        webhook_id = payload.webhook_id
        resource_id = payload.resource_id
    elif isinstance(payload, models.EventWebhookPayload):
        resource_name = payload.data.resource.name
        event_id = str(payload.data.id)
        user_id = payload.data.keycloak_id if payload.data else "unknown"
        webhook_id = payload.webhook_id
        resource_id = payload.data.resource.id
    else:
        logger.error("Invalid payload type for switch port end event.")
        return False

    try:
        # Use resource name directly as interface name
        interface_name = resource_name
        
        # Restore switch port to default VLAN
        switch_manager = switch.get_switch_port_manager()
        success = switch_manager.restore_port_to_default_vlan(interface_name)
        
        if success:
            logger.info(f"[{EVENT_END}] Successfully restored switch interface {interface_name} to default VLAN (Event ID: {event_id})")
            
            # Send success notification
            notification.send_switch_port_notification(
                webhook_id=webhook_id,
                user_id=user_id,
                resource_name=resource_name,
                success=True,
                event_id=event_id,
                resource_id=resource_id
            )
            
            # Send webhook log for successful restoration
            notification.send_webhook_log(
                webhook_id=webhook_id,
                event_type=EVENT_END,
                success=True,
                payload_data=json.dumps(payload.model_dump()),
                status_code=200,
                response=f"Switch port '{resource_name}' restored to default VLAN",
                retry_count=0,
                metadata={"resourceName": resource_name, "userId": user_id, "eventId": event_id},
                resource_id=resource_id
            )
        else:
            logger.error(f"[{EVENT_END}] Failed to restore switch interface {interface_name} to default VLAN (Event ID: {event_id})")
            
            # Send failure notification
            notification.send_switch_port_notification(
                webhook_id=webhook_id,
                user_id=user_id,
                resource_name=resource_name,
                success=False,
                error_message="Failed to restore switch port to default VLAN",
                event_id=event_id,
                resource_id=resource_id
            )
        
        return success
        
    except Exception as e:
        logger.error(f"Error restoring switch port '{resource_name}': {str(e)}")
        
        # Send failure notification
        notification.send_switch_port_notification(
            webhook_id=webhook_id,
            user_id=user_id,
            resource_name=resource_name,
            success=False,
            error_message=str(e),
            event_id=event_id,
            resource_id=resource_id
        )
        
        return False
