# Switch Port Webhook

A Python FastAPI webhook service for handling switch port reservation events. This service manages network switch VLAN configurations for individual port reservations.

This webhook has been developed to serve events produced by the [Cloud Resource Reservation System](https://github.com/giovannimirarchi420/cloud-resource-reservation), a comprehensive platform for managing cloud resource reservations with authentication, monitoring, and multi-service orchestration.

## Overview

This webhook receives switch port reservation events and configures/restores switch port VLAN assignments using Cisco IOS commands via SSH.

## Features

- **Switch Port Configuration**: Automatically assigns switch ports to specific VLANs based on custom parameters
- **VLAN Management**: Creates VLANs dynamically and manages port assignments
- **Port Restoration**: Restores ports to default VLAN when reservations end
- **Security**: HMAC signature verification for webhook security
- **Monitoring**: Health checks and comprehensive logging
- **Switch Integration**: Supports Cisco IOS switches via SSH/Netmiko

## Configuration

### Environment Variables

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `PORT` | integer | No | `5002` | HTTP server listening port |
| `LOG_LEVEL` | string | No | `INFO` | Logging level |
| `SWITCH_HOST` | string | Yes |  | Switch IP address or hostname |
| `SWITCH_USERNAME` | string | Yes |  | Switch SSH username |
| `SWITCH_PASSWORD` | string | Yes |  | Switch SSH password |
| `SWITCH_DEVICE_TYPE` | string | No | `cisco_ios` | Netmiko device type |
| `SWITCH_PORT` | integer | No | `22` | Switch SSH port |
| `SWITCH_TIMEOUT` | integer | No | `30` | Switch connection timeout |
| `DEFAULT_VLAN_ID` | integer | No | `10` | Default VLAN for port restoration |
| `WEBHOOK_SECRET` | string | No |  | Shared secret for HMAC verification |
| `NOTIFICATION_ENDPOINT` | string | No |  | External endpoint for notifications |
| `WEBHOOK_LOG_ENDPOINT` | string | No |  | External endpoint for webhook logs |
| `DISABLE_HEALTHZ_LOGS` | boolean | No | true | Disable healthz logs (for k8s probes) |

## API Endpoints

### POST /webhook
Processes switch port reservation lifecycle events and manages corresponding VLAN configurations.

**Expected Custom Parameters:**
- `vlan_id`: ID of the VLAN to assign to the switch port

**Expected Resource Naming:**
- Switch port resources should be named with the actual interface name (e.g., `GigabitEthernet1/0/1`, `Twe1/0/24`, `FastEthernet0/1`)
- The resource name will be used directly as the interface name in switch commands

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
    "resourceName": "GigabitEthernet1/0/1",
    "customParameters": "{\"vlan_id\": \"VLAN_USER_123\"}"
  }'
```

## Switch Configuration

This webhook configures Cisco IOS switches with the following operations:

### EVENT_START (Port Reservation)
1. Extracts VLAN ID from `vlan_id` field in `customParameters`
2. Creates the VLAN if it doesn't exist
3. Assigns the switch port to the VLAN
4. Enables the port

### EVENT_END (Port Release)
1. Restores the switch port to the default VLAN
2. Enables the port

## Example Webhook Payload

```json
{
{
   "eventType":"EVENT_START",
   "timestamp":"2025-07-06T08:55:07.5631405Z",
   "eventId":"103",
   "webhookId":3,
   "userId":"bdb072ee-eebd-4bf9-8ce3-bfeaadb95542",
   "username":"admin",
   "email":"test@example.it",
   "sshPublicKey":"ssh-rsa AAAAB3Nz...",
   "eventTitle":"Switch Port Reservation",
   "eventDescription":"",
   "eventStart":"2025-07-06T09:00:00Z",
   "eventEnd":"2025-07-06T09:54:09.536Z",
   "customParameters":"{\"vlan_id\":\"987\"}",
   "resourceId":4,
   "resourceName":"Hu1/0/1",
   "resourceType":"Switch Port",
   "resourceSpecs":"Switch 100Gbps, Hu1/0/1",
   "resourceLocation":"RESTART",
   "siteId":"59d52cfc-650c-41e6-9688-eb5ef0899968",
   "siteName":"Polito"
}
}
```

## Deployment

See the `Dockerfile` for containerized deployment.
