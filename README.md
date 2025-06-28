# Switch Port Webhook

A Python FastAPI webhook service for handling switch port reservation events. This service manages network switch VLAN configurations for individual port reservations.

This webhook has been developed to serve events produced by the [Cloud Resource Reservation System](https://github.com/giovannimirarchi420/cloud-resource-reservation), a comprehensive platform for managing cloud resource reservations with authentication, monitoring, and multi-service orchestration.

## Overview

This webhook receives switch port reservation events and configures/restores switch port VLAN assignments using Cisco IOS commands via SSH.

## Features

- **Switch Port Configuration**: Automatically assigns switch ports to specific VLANs based on custom parameters
- **VLAN Management**: Creates VLANs dynamically and manages port assignments
- **Port Restoration**: Restores ports to default VLAN when reservations end
- **Single Event Processing**: Processes individual switch port events (migrated from batch processing)
- **Security**: HMAC signature verification for webhook security
- **Monitoring**: Health checks and comprehensive logging
- **Switch Integration**: Supports Cisco IOS switches via SSH/Netmiko

## Key Differences from Original

This service is focused only on switch port VLAN configuration and does **NOT** include:
- Server provisioning/deprovisioning
- BareMetalHost management
- Kubernetes integration

## Configuration

### Environment Variables

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `PORT` | integer | No | `5002` | HTTP server listening port |
| `LOG_LEVEL` | string | No | `INFO` | Logging level |
| `SWITCH_HOST` | string | No | `192.168.24.67` | Switch IP address or hostname |
| `SWITCH_USERNAME` | string | No | `admin` | Switch SSH username |
| `SWITCH_PASSWORD` | string | No | `admin` | Switch SSH password |
| `SWITCH_DEVICE_TYPE` | string | No | `cisco_ios` | Netmiko device type |
| `SWITCH_PORT` | integer | No | `22` | Switch SSH port |
| `SWITCH_TIMEOUT` | integer | No | `30` | Switch connection timeout |
| `DEFAULT_VLAN_ID` | integer | No | `10` | Default VLAN for port restoration |
| `WEBHOOK_SECRET` | string | No | None | Shared secret for HMAC verification |
| `NOTIFICATION_ENDPOINT` | string | No | None | External endpoint for notifications |
| `WEBHOOK_LOG_ENDPOINT` | string | No | None | External endpoint for webhook logs |

## API Endpoints

### POST /webhook
Processes switch port reservation lifecycle events and manages corresponding VLAN configurations.

**Expected Custom Parameters:**
- `vlan_name`: Name of the VLAN to assign to the switch port

**Expected Resource Naming:**
- Switch port resources should be named: `switch-port-{port_number}` (e.g., `switch-port-1`, `switch-port-24`)

### GET /healthz
Health check endpoint for monitoring.

## Usage

```bash
# Start the service
python -m app.main

# Send a webhook event for switch port reservation
curl -X POST http://localhost:5002/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "eventType": "EVENT_START",
    "eventId": "event-123",
    "userId": "user-456",
    "username": "giovanni.mirarchi",
    "resourceType": "Switch Port",
    "resourceName": "switch-port-1",
    "customParameters": "{\"vlan_name\": \"VLAN_USER_123\"}"
  }'
```

## Switch Configuration

This webhook configures Cisco IOS switches with the following operations:

### EVENT_START (Port Reservation)
1. Extracts `vlan_name` from `customParameters`
2. Creates the VLAN if it doesn't exist
3. Assigns the switch port to the VLAN
4. Enables the port

### EVENT_END (Port Release)
1. Restores the switch port to the default VLAN (ID: 10)
2. Enables the port

## Example Webhook Payload

```json
{
  "eventType": "EVENT_START",
  "timestamp": "2025-06-28T14:30:00.000Z",
  "eventId": "event-123",
  "userId": "user-456",
  "username": "giovanni.mirarchi",
  "resourceType": "Switch Port",
  "resourceName": "switch-port-24",
  "customParameters": "{\"vlan_name\": \"VLAN_RESEARCH_LAB\"}"
}
```

## Deployment

See the `Dockerfile` for containerized deployment. The service can be deployed in Kubernetes alongside the server provisioning webhook.
