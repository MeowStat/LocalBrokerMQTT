# Architecture Overview

This document describes the overall system architecture of the **TinyML ESP32 IoT Gateway** project.

## System Overview

The system acts as a **local MQTT gateway** that bridges sensor data from ESP32 devices to a cloud platform (CoreIoT / ThingsBoard), while applying lightweight TinyML inference at the edge.

```
  [ESP32 Devices]
        |
        |  MQTT Publish
        |  topic: devices/{MAC}/telemetry
        v
 +----------------+
 |   TinyMQTT     |  <-- Local MQTT Broker (hbmqtt, port 1883)
 |  (Broker)      |      Runs on host/edge machine
 +----------------+
        |
        |  MQTT Subscribe
        |  topic: devices/+/telemetry
        v
 +----------------+
 |  TinyGateway   |  <-- Gateway Service (paho-mqtt)
 |  (Forwarder)   |
 +----------------+
        |
        |  MQTT Publish (v1/gateway/telemetry)
        |  ThingsBoard Gateway API
        v
 +----------------------+
 | CoreIoT / ThingsBoard |  <-- Cloud IoT Platform
 +----------------------+
```

---

## Components

### 1. TinyMQTT (Local Broker)
**File:** `TinyMQTT.py`

A local MQTT broker that acts as the central message hub for all ESP32 devices on the local network.

- **Role:** Receives all telemetry messages published by ESP32 devices.
- **Broker Engine:** [`hbmqtt`](https://hbmqtt.readthedocs.io/) — an asyncio-based MQTT broker.
- **Port:** `1883` (TCP)
- **Bind Address:** `0.0.0.0` (accepts connections from any device on the network)
- **Internal Monitor:** Runs a built-in `paho-mqtt` subscriber (as a background thread) that logs all received messages to the console and log file.

### 2. TinyGateway (Cloud Forwarder)
**File:** `TinyGateway.py`

A gateway service that subscribes to the local broker and forwards telemetry to the cloud.

- **Role:** Bridges the local MQTT broker and ThingsBoard cloud.
- **Upstream:** ThingsBoard / CoreIoT via the [ThingsBoard Gateway API](https://thingsboard.io/docs/reference/gateway-mqtt-api/).
- **Downstream:** Local broker at `mqtt-broker:1883` (Docker) or `127.0.0.1:1883` (local).
- **Topic Subscription:** `devices/+/telemetry`
- **Cloud Publish Topic:** `v1/gateway/telemetry`
- **Offline Buffering:** Uses SQLite (`buffer.db`) to persist messages when the cloud is unreachable.

---

## Data Flow

### Normal Operation (Online)
```
ESP32 → publish("devices/MAC/telemetry", JSON)
  → TinyMQTT Broker (receives message)
    → TinyGateway on_message callback
      → INSERT INTO buffer.db
        → buffer_worker thread reads row
          → Publish to ThingsBoard via "v1/gateway/telemetry"
            → DELETE row from buffer.db (on QoS 1 confirmation)
```

### Degraded Operation (Cloud Offline)
```
ESP32 → publish("devices/MAC/telemetry", JSON)
  → TinyMQTT Broker
    → TinyGateway on_message callback
      → INSERT INTO buffer.db  ← messages accumulate here
        (buffer_worker detects no connection, waits)

[When internet is restored]
  → buffer_worker detects is_tb_connected = True
    → Sequentially flushes all buffered rows to ThingsBoard
```

---

## Topic Convention

| Topic Pattern | Publisher | Subscriber |
|---|---|---|
| `devices/{device_id}/telemetry` | ESP32 device | TinyGateway |
| `v1/gateway/telemetry` | TinyGateway | ThingsBoard |
| `$SYS/#` | TinyMQTT Broker | Internal |

### Expected Payload Format
```json
{
  "temperature": 27.20,
  "humidity": 62.40,
  "vineyard_state": "NORMAL",
  "pump_status": "ON",
  "fan_status": "OFF",
  "anomaly_label": "Normal",
  "anomaly_score": 0.920
}
```

---

## Threading Model

### TinyMQTT
| Thread | Role |
|---|---|
| Main Thread | Runs the asyncio event loop for `hbmqtt` broker |
| `broker_thread` | Isolates broker's asyncio loop from main thread |
| `subscriber_thread` | Runs `paho-mqtt` loop to log all messages |

### TinyGateway
| Thread | Role |
|---|---|
| Main Thread | Runs `local_client.loop_forever()` (listens for ESP32 messages) |
| `tb_client` background | `paho-mqtt`'s `loop_start()` — handles ThingsBoard connection |
| `buffer_worker` thread | Reads from SQLite and flushes messages to ThingsBoard |

---

## Technology Stack

| Component | Technology | Version |
|---|---|---|
| Local MQTT Broker | `hbmqtt` | 0.9.6 |
| MQTT Client | `paho-mqtt` | 1.6.1 |
| WebSocket support | `websockets` | 8.1 |
| Python Runtime | Python | 3.8.5 |
| Offline Buffer | SQLite3 | (stdlib) |
| Logging | RotatingFileHandler | (stdlib) |
| Containerization | Docker + Docker Compose | — |
