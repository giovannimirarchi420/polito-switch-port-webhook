"""
Switch Port Webhook API endpoints.

This module provides FastAPI router with endpoints for processing webhook events
related to switch port resource reservations with VLAN configuration.
"""
from typing import Optional, List, Union
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Request, Header, HTTPException, status
from fastapi.responses import JSONResponse

from . import config, models, utils
from .services import security, switch, notification

logger = config.logger

# Constants for event types
EVENT_START = 'EVENT_START'
EVENT_END = 'EVENT_END'
EVENT_DELETED = 'EVENT_DELETED'

router = APIRouter()

async def _verify_webhook_signature(request: Request, signature: Optional[str]) -> bytes:
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


def _create_success_response(action: str, resource_name: str, user_id: Optional[str]) -> JSONResponse:
    """Create a standardized success response for single event operations."""
    return JSONResponse({
        "status": "success",
        "message": f"Successfully {action}d switch port '{resource_name}'",
        "userId": user_id
    })


def _handle_switch_port_start_event(
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
        vlan_name = utils.get_vlan_name_from_custom_params(custom_parameters)
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
                payload_data=payload.model_dump(),
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


def _handle_switch_port_end_event(
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
                payload_data=payload.model_dump(),
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


@router.post("/webhook")
async def handle_webhook(
    payload: Union[models.WebhookPayload, models.EventWebhookPayload],
    request: Request, 
    x_webhook_signature: Optional[str] = Header(None)
) -> JSONResponse:
    """
    Handle incoming webhook events for switch port reservations.
    Only processes events for Switch Port resource types.
    """
    logger.info(f"Received webhook request. Attempting to parse payload.")
    logger.debug(f"Payload: {payload}")
    raw_payload = await _verify_webhook_signature(request, x_webhook_signature)
    
    # Handle single event payload format
    if isinstance(payload, models.WebhookPayload):
        logger.info(
            f"Processing single switch port webhook event. Event Type: '{payload.event_type}', "
            f"User: '{payload.username}', Resource: '{payload.resource_name}', "
            f"Resource Type: '{payload.resource_type}'."
        )

        # Check if this is a Switch Port resource type
        if payload.resource_type != "Switch Port":
            logger.info(f"Skipping non-Switch Port resource '{payload.resource_name}' of type '{payload.resource_type}'. No action taken.")
            return JSONResponse({
                "status": "success",
                "message": f"No action needed for resource type '{payload.resource_type}'."
            })

        # Process the single switch port event
        if payload.event_type == EVENT_START:
            if _handle_switch_port_start_event(
                payload
            ):
                return _create_success_response("configure", payload.resource_name, payload.user_id)
            else:
                logger.error(f"Failed to configure switch port '{payload.resource_name}' for event {payload.event_id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to configure switch port '{payload.resource_name}'"
                )

        elif payload.event_type == EVENT_END:
            if _handle_switch_port_end_event(
                payload
            ):
                return _create_success_response("restore", payload.resource_name, payload.user_id)
            else:
                logger.error(f"Failed to restore switch port '{payload.resource_name}' for event {payload.event_id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to restore switch port '{payload.resource_name}'"
                )
        else:
            logger.info(f"No action configured for event type '{payload.event_type}'.")
            return JSONResponse({
                "status": "success",
                "message": f"No action needed for event type '{payload.event_type}'."
            })

    elif isinstance(payload, models.EventWebhookPayload):
        logger.info(
            f"Processing switch port {payload.event_type} webhook. "
            f"Resource Name: '{payload.data.resource.name}'."
        )
        
        if payload.event_type == EVENT_DELETED:
            now = payload.timestamp # Use timestamp from the payload
            
            # Ensure start and end times are offset-aware for comparison with offset-aware 'now'
            reservation_start = payload.data.start
            reservation_end = payload.data.end

            logger.debug(f"Current time (UTC): {now}, Reservation Start: {reservation_start}, Reservation End: {reservation_end}")

            if reservation_start <= now < reservation_end:
                logger.info(f"Reservation for switch port '{payload.data.resource.name}' is currently active. Restoring to default VLAN.")
                if _handle_switch_port_end_event(
                    payload
                ):
                    logger.info(f"Successfully restored switch port '{payload.data.resource.name}' to default VLAN due to EVENT_DELETED.")
                    return JSONResponse({
                        "status": "success", 
                        "message": f"Switch port '{payload.data.resource.name}' restored to default VLAN due to active reservation deletion."
                    })
                else:
                    logger.error(f"Failed to restore switch port '{payload.data.resource.name}' for EVENT_DELETED.")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to restore switch port '{payload.data.resource.name}' after EVENT_DELETED."
                    )
            else:
                logger.info(f"Reservation for switch port '{payload.data.resource.name}' is not currently active. No action taken for EVENT_DELETED.")
                return JSONResponse({
                    "status": "success",
                    "message": f"No action taken for switch port '{payload.data.resource.name}' as reservation is not currently active."
                })
        else:
            return JSONResponse({
                "status": "success",
                "message": f"No action needed for event type '{payload.event_type}'."
            })
    else:
        # If event type is not recognized, return success with no action needed
        event_type_to_log = payload.event_type if hasattr(payload, 'event_type') else "unknown"
        username_to_log = payload.username if isinstance(payload, models.WebhookPayload) and hasattr(payload, 'username') else "N/A"
        
        logger.info(f"Received event type '{event_type_to_log}' for user {username_to_log}. No action configured for this event type.")
        return JSONResponse({
            "status": "success",
            "message": f"No action needed for event type '{event_type_to_log}'."
        })


@router.get("/healthz")
def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "switch-port-webhook"}
