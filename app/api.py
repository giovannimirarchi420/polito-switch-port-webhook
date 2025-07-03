"""
Switch Port Webhook API endpoints.

This module provides FastAPI router with endpoints for processing webhook events
related to switch port resource reservations with VLAN configuration.
"""
from typing import Optional, Union

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
    raw_payload = await utils.verify_webhook_signature(request, x_webhook_signature)
    
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
            if utils.handle_switch_port_start_event(
                payload
            ):
                return utils.create_success_response("configure", payload.resource_name, payload.user_id)
            else:
                logger.error(f"Failed to configure switch port '{payload.resource_name}' for event {payload.event_id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to configure switch port '{payload.resource_name}'"
                )

        elif payload.event_type == EVENT_END:
            if utils.handle_switch_port_end_event(
                payload
            ):
                return utils.create_success_response("restore", payload.resource_name, payload.user_id)
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
            now = utils.parse_timestamp(payload.timestamp) # Parse timestamp from string to datetime
            
            # Parse start and end times from string to datetime
            reservation_start = utils.parse_timestamp(payload.data.start)
            reservation_end = utils.parse_timestamp(payload.data.end)

            logger.debug(f"Current time (UTC): {now}, Reservation Start: {reservation_start}, Reservation End: {reservation_end}")

            if reservation_start <= now < reservation_end:
                logger.info(f"Reservation for switch port '{payload.data.resource.name}' is currently active. Restoring to default VLAN.")
                if utils.handle_switch_port_end_event(
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
