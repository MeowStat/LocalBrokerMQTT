# TinyML_ESP32

> 📚 **Documentation:** See the [`docs/`](./docs/) folder for [Architecture](./docs/architecture.md), [Features](./docs/features.md), and [Docker Deployment Guide](./docs/docker.md).
# TinyML_ESP32 Gateway

## Running the Services

You can run both the MQTT Broker (`TinyMQTT.py`) and the Gateway (`TinyGateway.py`) simultaneously using either **Docker** (Recommended) or a local shell script.

### Method 1: Using Docker (Recommended)
This is the easiest method and completely avoids Python dependency issues.

1. Ensure you have Docker and Docker Compose installed.
2. Run the services in the background:
   ```bash
   docker-compose up -d
   ```
3. To view logs:
   ```bash
   docker-compose logs -f
   ```
4. To stop the services:
   ```bash
   docker-compose down
   ```

### Method 2: Using Shell Script (Local setup)
If you prefer running without Docker, a convenience script has been provided.

### Usage

1. Make sure the script has execution permissions:
   ```bash
   chmod +x run_services.sh
   ```

2. Run the script:
   ```bash
   ./run_services.sh
   ```

### What the script does:
- Starts the `TinyMQTT.py` broker in the background.
- Waits a couple of seconds to ensure the broker is initialized.
- Starts `TinyGateway.py` in the background.
- Monitors both processes.
- Gracefully shuts down both processes when you press `Ctrl+C`.

### Prerequisites
This project requires a specific Python environment due to dependencies on `hbmqtt` and older versions of `asyncio`. It is highly recommended to use **Miniconda** (or Anaconda) with **Python 3.8.5**.

#### Required Libraries:
- `hbmqtt == 0.9.6`
- `websockets == 8.1`
- `paho-mqtt == 1.6.1`

#### Environment Setup
You can easily create the required environment using the provided `environment.yml`:
```bash
conda env create -f environment.yml
```

Or manually create it:
```bash
conda create -n tinymqtt python=3.8.5 -y
conda activate tinymqtt
pip install hbmqtt==0.9.6 websockets==8.1 paho-mqtt==1.6.1
```

Make sure to activate the environment before running the scripts:
```bash
conda activate tinymqtt
```

## Security Hardening (Phase 5)

By default, the `TinyMQTT.py` broker allows anonymous connections to make local development easier. If you are deploying this in a network where you want to restrict who can publish telemetry data, you should enable password authentication.

### How to Enable Password Auth:
1. Open `TinyMQTT.py` and locate the `broker_config` dictionary.
2. Change `allow-anonymous` to `False`.
3. Uncomment the `plugins` and `password-file` lines:
   ```python
   'auth': {
       'allow-anonymous': False,
       'plugins': ['auth_file'],
       'password-file': 'password_file.txt'
   }
   ```
4. Create a `password_file.txt` in the root directory. You can use the `hbmqtt_passwd` utility (installed with `hbmqtt`) to generate passwords.
5. Restart the broker (`docker-compose restart mqtt-broker`).
