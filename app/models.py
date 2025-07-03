"""
Pydantic models for switch port webhook payload validation.

This module defines the data models used for validating incoming webhook payloads.
Only handles Switch Port resource types.
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class WebhookPayload(BaseModel):
    """
    Model for webhook event payload.
    Handles a single Switch Port event.
    """
    event_type: str = Field(..., alias='eventType', description="Type of the event (EVENT_START, EVENT_END)")
    timestamp: datetime = Field(..., description="Timestamp when the event occurred")
    event_id: str = Field(..., alias='eventId', description="Unique identifier for the event")
    webhook_id: int = Field(..., alias='webhookId', description="Unique identifier for the webhook")
    user_id: Optional[str] = Field(None, alias='userId', description="ID of the user associated with the event")
    username: Optional[str] = Field(None, description="Username of the user")
    email: Optional[str] = Field(None, description="Email address of the user")
    ssh_public_key: Optional[str] = Field(None, alias='sshPublicKey', description="SSH public key for resource access")
    event_title: Optional[str] = Field(None, alias='eventTitle', description="Title of the reservation event")
    event_description: Optional[str] = Field(None, alias='eventDescription', description="Description of the event")
    event_start: datetime = Field(..., alias='eventStart', description="Start time of the event")
    event_end: datetime = Field(..., alias='eventEnd', description="End time of the event")
    custom_parameters: Optional[str] = Field(None, alias='customParameters', description="JSON serialized string of custom parameters")
    resource_id: int = Field(..., alias='resourceId', description="Identifier of the resource")
    resource_name: str = Field(..., alias='resourceName', description="Name of the switch port resource")
    resource_type: str = Field(..., alias='resourceType', description="Type of the resource - must be 'Switch Port'")
    resource_specs: Optional[str] = Field(None, alias='resourceSpecs', description="Specifications of the resource")
    resource_location: Optional[str] = Field(None, alias='resourceLocation', description="Location of the resource")
    site_id: Optional[str] = Field(None, alias='siteId', description="Identifier of the site")
    site_name: Optional[str] = Field(None, alias='siteName', description="Name of the site")


class EventResourceInfo(BaseModel):
    """Model for resource information within EVENT_DELETED data."""
    name: str = Field(..., description="Name of the resource to be released")


class EventData(BaseModel):
    """Model for the 'data' field in an EVENT_DELETED payload."""
    id: int = Field(..., description="Unique identifier for the deletion event data")
    start: datetime = Field(..., description="Original start time of the reservation")
    end: datetime = Field(..., description="Original end time of the reservation")
    custom_parameters: Optional[str] = Field(None, alias='customParameters', description="JSON serialized string of custom parameters")
    resource: EventResourceInfo = Field(..., description="Details of the resource associated with the event")
    keycloak_id: Optional[str] = Field(None, alias='keycloakId', description="Keycloak ID of the user")


class EventWebhookPayload(BaseModel):
    """Model for EVENT_DELETED webhook payload."""
    event_type: str = Field(..., alias='eventType', description="Type of the event, should be EVENT_DELETED")
    timestamp: datetime = Field(..., description="Timestamp when the event occurred")
    data: EventData = Field(..., description="Detailed data for the EVENT_DELETED event")
