import paho.mqtt.client as mqtt
import json
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# --------------------------------------
# Configuration
# --------------------------------------
THINGSBOARD_HOST = 'app.coreiot.io'
THINGSBOARD_PORT = 1883
ACCESS_TOKEN = 'snFgWllzx57Vk6KRoodS'

LOCAL_HOST = '127.0.0.1'
LOCAL_PORT = 1883
LOCAL_TOPIC = 'devices/+/telemetry'  # e.g. devices/CCBA970DEB20/telemetry

# --------------------------------------
# ThingsBoard client (upstream)
# --------------------------------------
def on_tb_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to ThingsBoard (%s:%s)", THINGSBOARD_HOST, THINGSBOARD_PORT)
    else:
        logger.error("Failed to connect to ThingsBoard (rc=%s)", rc)

tb_client = mqtt.Client("TinyGateway_TB")
tb_client.username_pw_set(ACCESS_TOKEN)
tb_client.on_connect = on_tb_connect
tb_client.connect(THINGSBOARD_HOST, THINGSBOARD_PORT, 60)
tb_client.loop_start()

# --------------------------------------
# Local broker client (downstream)
# --------------------------------------
def on_local_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to local broker, subscribing to '%s'", LOCAL_TOPIC)
        client.subscribe(LOCAL_TOPIC, qos=0)
    else:
        logger.error("Failed to connect to local broker (rc=%s)", rc)

def on_message(client, userdata, msg):
    try:
        parts = msg.topic.split("/")
        device_id = parts[1]  # devices/ESP32_001/sensors → ESP32_001
        values = json.loads(msg.payload.decode("utf-8"))

        telemetry = {
            device_id: [{"ts": int(time.time() * 1000), "values": values}]
        }
        result = tb_client.publish("v1/gateway/telemetry", json.dumps(telemetry))
        logger.info("Forwarded [%s] → ThingsBoard (rc=%s)", device_id, result.rc)
    except json.JSONDecodeError:
        logger.error("Invalid JSON payload on topic %s: %s", msg.topic, msg.payload)
    except IndexError:
        logger.error("Unexpected topic format: %s", msg.topic)

local_client = mqtt.Client("TinyGateway_Local")
local_client.on_connect = on_local_connect
local_client.on_message = on_message

# --------------------------------------
# Run
# --------------------------------------
try:
    local_client.connect(LOCAL_HOST, LOCAL_PORT, 60)
    local_client.loop_forever()
except KeyboardInterrupt:
    logger.info("Interrupted, shutting down")
finally:
    local_client.disconnect()
    tb_client.loop_stop()
    tb_client.disconnect()
