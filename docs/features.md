# Features

This document describes the features implemented across the **TinyMQTT** broker and **TinyGateway** services.

---

## TinyMQTT — Local MQTT Broker

### F1: Local MQTT Broker
- Starts a fully functional MQTT broker on **port 1883** bound to `0.0.0.0`, making it accessible to all devices on the local network.
- Powered by `hbmqtt`, which runs on Python's `asyncio` event loop.
- Each service runs in its own isolated thread with its own event loop to avoid conflicts.

### F2: Internal Message Monitor
- A built-in `paho-mqtt` subscriber (running in a dedicated background thread) subscribes to **all topics** (`#`).
- Logs each incoming message in the format:
  ```
  [device_mac] topic=devices/.../telemetry payload={...}
  ```
- Useful for real-time debugging and observability without additional tools.

### F3: Authentication Support (Configurable)
- By default, the broker allows **anonymous connections** for ease of development.
- The broker configuration in `broker_config` supports switching to **file-based password authentication** by:
  - Setting `allow-anonymous: False`
  - Enabling `auth_file` plugin
  - Pointing to a `password_file.txt`
- See [Security Guide](./docker.md#security-hardening) for details.

### F4: Topic Taboo Check
- The broker has **topic-check** enabled with the `topic_taboo` plugin to prevent publishing to restricted system topics.

### F5: Rotating File Logging
- All broker activity is logged to both the console **and** a rotating file at `logs/broker.log`.
- File size limit: **5MB** per file.
- Backup count: **3** rotated files kept, older files are auto-deleted.

---

## TinyGateway — Cloud Bridge

### F6: Bidirectional MQTT Bridge
- Subscribes to `devices/+/telemetry` on the **local broker**.
- Translates and republishes each message to `v1/gateway/telemetry` on **ThingsBoard / CoreIoT** using the ThingsBoard Gateway API.

### F7: Device-Scoped Telemetry Formatting
- Automatically extracts the `device_id` from the topic (`devices/{device_id}/telemetry`).
- Reformats the payload into ThingsBoard's expected gateway structure:
  ```json
  {
    "ESP32_001": [{"ts": 1716480000000, "values": {...}}]
  }
  ```
- Timestamps (`ts`) are added automatically in milliseconds.

### F8: Offline Buffering (SQLite)
- When the internet/ThingsBoard is unreachable, **no telemetry data is lost**.
- Each incoming message is immediately written to a local SQLite database (`buffer.db`) before any forwarding attempt.
- A **background worker thread** monitors cloud connectivity and flushes buffered messages in order when the connection is restored.
- Messages are only deleted from the buffer after ThingsBoard confirms receipt via **QoS 1** (`wait_for_publish()`).

### F9: Connection State Tracking
- The gateway tracks the ThingsBoard connection status in real-time using the `on_tb_connect` and `on_tb_disconnect` callbacks.
- The buffer worker reads this flag (`is_tb_connected`) to decide whether to attempt forwarding.
- Disconnection events are logged as `[WARNING]` for easy identification.

### F10: Thread-Safe Database Access
- All reads and writes to `buffer.db` are protected with a `threading.Lock()`.
- Prevents race conditions between the `on_message` callback (writer) and the `buffer_worker` thread (reader/deleter).

### F11: Environment-Based Configuration
- All sensitive configuration (ThingsBoard host, port, access token) and service addresses are read from **environment variables** with sane defaults.

| Variable | Default | Description |
|---|---|---|
| `THINGSBOARD_HOST` | `app.coreiot.io` | ThingsBoard server hostname |
| `THINGSBOARD_PORT` | `1883` | ThingsBoard MQTT port |
| `ACCESS_TOKEN` | *(set in .env)* | Device/gateway access token |
| `LOCAL_BROKER_HOST` | `127.0.0.1` | Local MQTT broker address |
| `LOCAL_BROKER_PORT` | `1883` | Local MQTT broker port |

### F12: Graceful Shutdown
- Handles `KeyboardInterrupt` cleanly by:
  - Disconnecting from the local broker
  - Stopping the ThingsBoard client loop
  - Closing the SQLite database connection

### F13: Rotating File Logging
- All gateway activity is logged to both the console **and** a rotating file at `logs/gateway.log`.
- File size limit: **5MB** per file.
- Backup count: **3** rotated files kept.
