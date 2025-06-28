"""
Switch Port Webhook API endpoints.

This module provides FastAPI router with endpoints for processing webhook events
related to switch port resource reservations with VLAN configuration.
"""
from typing import Optional, List, Union
from datetime import datetime
import uuid

from fastapi import FastAPI, Request, Header, HTTPException, status
from fastapi.responses import JSONResponse

from . import config, models, utils
from .services import security, switch, notification

logger = config.logger

# Constants for event types
EVENT_START = 'EVENT_START'
EVENT_END = 'EVENT_END'
EVENT_DELETED = 'EVENT_DELETED'

# Create FastAPI app
app = FastAPI(
    title="Switch Port Webhook",
    description="Webhook service for switch port VLAN configuration",
    version="1.0.0"
)


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


def _create_batch_success_response(action: str, count: int, user_id: Optional[str]) -> JSONResponse:
    """Create a standardized success response for batch operations."""
    return JSONResponse({
        "status": "success",
        "message": f"Successfully {action}ed {count} switch port(s)",
        "userId": user_id,
        "timestamp": datetime.now().isoformat()
    })


def _handle_switch_port_start_event(
    resource_name: str,
    custom_parameters: Optional[str],
    webhook_id: str,
    user_id: str,
    event_id: Optional[str] = None
) -> bool:
    """
    Handle switch port reservation start event. Returns True on success.
    """
    try:
        # Extract VLAN name from custom parameters
        vlan_name = utils.get_vlan_name_from_custom_params(custom_parameters)
        if not vlan_name:
            logger.error(f"No vlan_name found in custom parameters for switch port '{resource_name}'")
            return False
        
        # Extract port number from resource name
        port_number = utils.extract_port_number_from_resource_name(resource_name)
        if not port_number:
            logger.error(f"Could not extract port number from resource name '{resource_name}'")
            return False
        
        # Configure switch port with VLAN
        switch_manager = switch.get_switch_port_manager()
        success = switch_manager.configure_switch_port(port_number, vlan_name)
        
        if success:
            logger.info(f"[{EVENT_START}] Successfully configured switch port {port_number} with VLAN '{vlan_name}' (Event ID: {event_id})")
            
            # Send success notification
            notification.send_switch_port_notification(
                webhook_id=webhook_id,
                user_id=user_id,
                resource_name=resource_name,
                success=True,
                event_id=event_id
            )
            
            # Send webhook log for successful configuration
            notification.send_webhook_log(
                webhook_id=webhook_id,
                event_type=EVENT_START,
                success=True,
                status_code=200,
                response_message=f"Switch port '{resource_name}' configured with VLAN '{vlan_name}'",
                retry_count=0,
                resource_name=resource_name,
                user_id=user_id,
                event_id=event_id
            )
        else:
            logger.error(f"[{EVENT_START}] Failed to configure switch port {port_number} with VLAN '{vlan_name}' (Event ID: {event_id})")
            
            # Send failure notification
            notification.send_switch_port_notification(
                webhook_id=webhook_id,
                user_id=user_id,
                resource_name=resource_name,
                success=False,
                error_message=f"Failed to configure switch port with VLAN '{vlan_name}'",
                event_id=event_id
            )
        
        return success
        
    except Exception as e:
        logger.error(f"Error configuring switch port '{resource_name}': {str(e)}")
        
        # Send failure notification
        notification.send_switch_port_notification(
            webhook_id=webhook_id,
            user_id=user_id,
            resource_name=resource_name,
            success=False,
            error_message=str(e),
            event_id=event_id
        )
        
        return False


def _handle_switch_port_end_event(
    resource_name: str,
    webhook_id: str,
    user_id: str,
    event_id: Optional[str] = None
) -> bool:
    """
    Handle switch port reservation end event. Returns True on success.
    """
    try:
        # Extract port number from resource name
        port_number = utils.extract_port_number_from_resource_name(resource_name)
        if not port_number:
            logger.error(f"Could not extract port number from resource name '{resource_name}'")
            return False
        
        # Restore switch port to default VLAN
        switch_manager = switch.get_switch_port_manager()
        success = switch_manager.restore_port_to_default_vlan(port_number)
        
        if success:
            logger.info(f"[{EVENT_END}] Successfully restored switch port {port_number} to default VLAN (Event ID: {event_id})")
            
            # Send success notification
            notification.send_switch_port_notification(
                webhook_id=webhook_id,
                user_id=user_id,
                resource_name=resource_name,
                success=True,
                event_id=event_id
            )
            
            # Send webhook log for successful restoration
            notification.send_webhook_log(
                webhook_id=webhook_id,
                event_type=EVENT_END,
                success=True,
                status_code=200,
                response_message=f"Switch port '{resource_name}' restored to default VLAN",
                retry_count=0,
                resource_name=resource_name,
                user_id=user_id,
                event_id=event_id
            )
        else:
            logger.error(f"[{EVENT_END}] Failed to restore switch port {port_number} to default VLAN (Event ID: {event_id})")
            
            # Send failure notification
            notification.send_switch_port_notification(
                webhook_id=webhook_id,
                user_id=user_id,
                resource_name=resource_name,
                success=False,
                error_message="Failed to restore switch port to default VLAN",
                event_id=event_id
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
            event_id=event_id
        )
        
        return False


@app.post("/webhook")
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
    
    raw_payload = await _verify_webhook_signature(request, x_webhook_signature)
    
    # Log based on the payload structure
    if isinstance(payload, models.WebhookPayload):
        active_resources_count = len(payload.active_resources) if payload.active_resources else 0
        logger.info(
            f"Processing switch port webhook. Event Type: '{payload.event_type}', "
            f"User: '{payload.username}', Event Count: {payload.event_count}, "
            f"Active Resources Count: {active_resources_count}."
        )

        # Filter events to only include Switch Port resource types
        switch_port_events = [event for event in payload.events if event.resource_type == "Switch Port"]
        if len(switch_port_events) != len(payload.events):
            logger.info(f"Filtered {len(payload.events) - len(switch_port_events)} non-Switch Port events. Processing {len(switch_port_events)} Switch Port events.")
        
        if not switch_port_events:
            logger.info("No Switch Port events found in payload. No action taken.")
            return JSONResponse({
                "status": "success",
                "message": "No Switch Port events to process."
            })

        # Log active resources if present (only Switch Ports)
        if payload.active_resources:
            active_switch_ports = [res for res in payload.active_resources if res.resource_type == "Switch Port"]
            if active_switch_ports:
                logger.info(f"User '{payload.username}' has {len(active_switch_ports)} active Switch Port resources:")
                for active_resource in active_switch_ports:
                    logger.info(
                        f"  - Active Switch Port: '{active_resource.resource_name}' "
                        f"Event: '{active_resource.event_title}' (until {active_resource.event_end})"
                    )
        else:
            logger.info(f"User '{payload.username}' has no active Switch Port resources at this time.")
            
        processed_events_count = 0
        failed_event_details = []

        if payload.event_type == EVENT_START:
            for event in switch_port_events:
                if _handle_switch_port_start_event(
                    event.resource_name,
                    event.custom_parameters,
                    payload.webhook_id,
                    payload.user_id or "unknown",
                    event.event_id
                ):
                    processed_events_count += 1
                else:
                    failed_event_details.append({"event_id": event.event_id, "resource_name": event.resource_name, "action": "configure"})

        elif payload.event_type == EVENT_END:
            for event in switch_port_events:
                if _handle_switch_port_end_event(
                    event.resource_name,
                    payload.webhook_id,
                    payload.user_id or "unknown",
                    event.event_id
                ):
                    processed_events_count += 1
                else:
                    failed_event_details.append({"event_id": event.event_id, "resource_name": event.resource_name, "action": "restore"})
        
        if failed_event_details:
            logger.error(f"Switch port webhook processing for user {payload.username} (Event Type: {payload.event_type}) encountered {len(failed_event_details)} failures out of {len(switch_port_events)} events.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Processing for event type '{payload.event_type}' failed for {len(failed_event_details)} out of {len(switch_port_events)} Switch Port events. Failures: {failed_event_details}"
            )
        
        # If all events (if any) were processed successfully
        return _create_batch_success_response(payload.event_type.lower(), processed_events_count, payload.user_id)

    elif isinstance(payload, models.EventWebhookPayload):
        logger.info(
            f"Processing switch port EVENT_DELETED webhook. "
            f"Webhook ID: '{payload.webhook_id}', Resource Name: '{payload.data.resource.name}'."
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
                    payload.data.resource.name,
                    payload.webhook_id,
                    payload.data.keycloak_id if payload.data else "unknown",
                    str(payload.data.id)
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


@app.get("/healthz")
def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "switch-port-webhook"}
