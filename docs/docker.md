# Docker Deployment Guide

This document covers how to build, run, and manage the **TinyMQTT** and **TinyGateway** services using Docker and Docker Compose.

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- [Docker Compose](https://docs.docker.com/compose/) installed (v2+)

---

## Project Structure

```
TinyML_ESP32/
├── Dockerfile                # Single image for both services
├── docker-compose.yml        # Orchestrates mqtt-broker + gateway
├── requirements_docker.txt   # Minimal Python dependencies for Docker
├── .env                      # Your secret credentials (NOT committed)
├── .env.example              # Template for .env
├── TinyMQTT.py               # MQTT Broker service
├── TinyGateway.py            # Cloud Gateway service
└── logs/                     # Auto-generated log directory (bind-mounted)
    ├── broker.log
    └── gateway.log
```

---

## Setup

### 1. Configure Environment Variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Then edit `.env`:
```dotenv
THINGSBOARD_HOST=app.coreiot.io
THINGSBOARD_PORT=1883
ACCESS_TOKEN=your_gateway_access_token_here
```

> **Note:** The `.env` file is listed in `.gitignore` and will never be committed to version control.

---

### 2. Build and Start Services

```bash
docker-compose up -d --build
```

This will:
1. Pull the base `python:3.8.5-slim` image.
2. Upgrade `pip` to the latest version.
3. Install `hbmqtt==0.9.6`, `websockets==8.1`, and `paho-mqtt==1.6.1`.
4. Copy the source code into the image.
5. Start two containers: `tinymqtt_broker` and `tinymqtt_gateway`.

---

## Managing Services

### View Live Logs
```bash
docker-compose logs -f
```

To see logs for a specific service only:
```bash
docker-compose logs -f gateway
docker-compose logs -f mqtt-broker
```

### Stop Services
```bash
docker-compose down
```

### Restart Services (after code changes)
Because the project directory is **bind-mounted** into the containers (`volumes: .:/app`), code changes are reflected immediately without a rebuild:
```bash
docker-compose restart
```

Only run `--build` again if you change `requirements_docker.txt` or `Dockerfile`:
```bash
docker-compose up -d --build
```

---

## Services Description

### `mqtt-broker` Container
| Property | Value |
|---|---|
| Image | Built from `Dockerfile` |
| Container Name | `tinymqtt_broker` |
| Command | `python3 TinyMQTT.py` |
| Exposed Port | `1883:1883` (TCP, MQTT) |
| Restart Policy | `always` |
| Log File | `logs/broker.log` |

### `gateway` Container
| Property | Value |
|---|---|
| Image | Built from `Dockerfile` (same image) |
| Container Name | `tinymqtt_gateway` |
| Command | `python3 TinyGateway.py` |
| Exposed Port | None (internal only) |
| Depends On | `mqtt-broker` |
| Restart Policy | `always` |
| Log File | `logs/gateway.log` |
| Key Env Var | `LOCAL_BROKER_HOST=mqtt-broker` |

> The gateway uses the service name `mqtt-broker` as the hostname to communicate with the broker over Docker's internal bridge network.

---

## Networking

Docker Compose creates a default bridge network (`tinyml_esp32_default`). Both containers are connected to this network and can reach each other by **service name**:

```
tinymqtt_gateway → mqtt-broker:1883   (internal Docker DNS)
HOST_MACHINE     → localhost:1883     (exposed port for ESP32 devices)
```

---

## Logs

Both services write logs to the `logs/` directory in the project root (bind-mounted from the host). Log files rotate automatically:
- Max size: **5 MB** per file
- Backups kept: **3** rotated files

```
logs/
├── broker.log          ← Active log
├── broker.log.1        ← Previous rotation
├── broker.log.2        ← Older rotation
└── gateway.log
```

The `logs/` directory is listed in `.gitignore` to prevent log files from being committed.

---

## Security Hardening

> By default, anonymous connections are **allowed** for ease of development.

To restrict access in production:

1. Open `TinyMQTT.py` and locate `broker_config`.
2. Modify the `auth` section:
   ```python
   'auth': {
       'allow-anonymous': False,
       'plugins': ['auth_file'],
       'password-file': 'password_file.txt'
   }
   ```
3. Generate a password file using the `hbmqtt_passwd` utility:
   ```bash
   # Inside the container or conda environment
   hbmqtt_passwd -c password_file.txt mydevice mysecretpassword
   ```
4. Make sure ESP32 devices use `username`/`password` when connecting to port `1883`.
5. Restart the broker:
   ```bash
   docker-compose restart mqtt-broker
   ```

---

## Dockerfile Reference

```dockerfile
FROM python:3.8.5-slim

WORKDIR /app

COPY requirements_docker.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements_docker.txt

COPY . .

CMD ["python3", "TinyMQTT.py"]
```

The `CMD` is overridden per-service in `docker-compose.yml`, so the same image runs both `TinyMQTT.py` and `TinyGateway.py`.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `Connection reset by peer` during build | Outdated `pip` failing TLS handshake | Ensure `RUN pip install --upgrade pip` is in `Dockerfile` |
| Gateway disconnects from ThingsBoard repeatedly | Wrong `ACCESS_TOKEN` or server firewall | Verify credentials in `.env` |
| `IncompleteReadError` in broker logs | Client disconnected abruptly (normal behavior in hbmqtt) | Safe to ignore — broker continues working |
| No `Forwarded` logs in gateway | ThingsBoard not reachable | Messages are buffered in `buffer.db` and will be flushed on reconnect |
