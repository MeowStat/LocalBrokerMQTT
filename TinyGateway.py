import paho.mqtt.client as mqtt
import json
import logging
import time
import os
import sqlite3
import threading

from logging.handlers import RotatingFileHandler

os.makedirs('logs', exist_ok=True)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

# Console handler
ch = logging.StreamHandler()
ch.setFormatter(formatter)
root_logger.addHandler(ch)

# Rotating file handler (5MB per file, keep 3 backups)
fh = RotatingFileHandler('logs/gateway.log', maxBytes=5*1024*1024, backupCount=3)
fh.setFormatter(formatter)
root_logger.addHandler(fh)

logger = logging.getLogger(__name__)

# --------------------------------------
# Configuration
# --------------------------------------
THINGSBOARD_HOST = os.environ.get('THINGSBOARD_HOST', 'app.coreiot.io')
THINGSBOARD_PORT = int(os.environ.get('THINGSBOARD_PORT', 1883))
ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN', 'snFgWllzx57Vk6KRoodS')

LOCAL_HOST = os.environ.get('LOCAL_BROKER_HOST', '127.0.0.1')
LOCAL_PORT = int(os.environ.get('LOCAL_BROKER_PORT', 1883))
LOCAL_TOPIC = 'devices/+/telemetry'  # e.g. devices/CCBA970DEB20/telemetry

# --------------------------------------
# Database Setup (Offline Buffering)
# --------------------------------------
db_lock = threading.Lock()
db_conn = sqlite3.connect('buffer.db', check_same_thread=False)
with db_lock:
    db_conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            telemetry_json TEXT
        )
    ''')
    db_conn.commit()

# --------------------------------------
# ThingsBoard client (upstream)
# --------------------------------------
is_tb_connected = False

def on_tb_connect(client, userdata, flags, rc):
    global is_tb_connected
    if rc == 0:
        is_tb_connected = True
        logger.info("Connected to ThingsBoard (%s:%s)", THINGSBOARD_HOST, THINGSBOARD_PORT)
    else:
        is_tb_connected = False
        logger.error("Failed to connect to ThingsBoard (rc=%s)", rc)

def on_tb_disconnect(client, userdata, rc):
    global is_tb_connected
    is_tb_connected = False
    logger.warning("Disconnected from ThingsBoard")

tb_client = mqtt.Client("TinyGateway_TB")
tb_client.username_pw_set(ACCESS_TOKEN)
tb_client.on_connect = on_tb_connect
tb_client.on_disconnect = on_tb_disconnect
tb_client.connect(THINGSBOARD_HOST, THINGSBOARD_PORT, 60)
tb_client.loop_start()

# --------------------------------------
# Offline Buffer Worker Thread
# --------------------------------------
def buffer_worker():
    while True:
        try:
            if is_tb_connected:
                row = None
                with db_lock:
                    c = db_conn.cursor()
                    c.execute("SELECT id, device_id, telemetry_json FROM messages ORDER BY id ASC LIMIT 1")
                    row = c.fetchone()
                
                if row:
                    msg_id, device_id, telemetry_json = row
                    # publish with QoS 1 to get delivery confirmation
                    result = tb_client.publish("v1/gateway/telemetry", telemetry_json, qos=1)
                    
                    try:
                        result.wait_for_publish(timeout=5.0)
                        if result.is_published():
                            with db_lock:
                                c = db_conn.cursor()
                                c.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
                                db_conn.commit()
                            logger.info("Forwarded [%s] → ThingsBoard (Buffered msg_id=%s)", device_id, msg_id)
                        else:
                            time.sleep(2)
                    except ValueError:
                        time.sleep(2)
                    except RuntimeError:
                        time.sleep(2)
                else:
                    time.sleep(1) # No messages in queue
            else:
                time.sleep(2) # Wait for connection to be established
        except Exception as e:
            logger.error("Buffer worker error: %s", e)
            time.sleep(2)

worker_thread = threading.Thread(target=buffer_worker, daemon=True)
worker_thread.start()

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
        device_id = parts[1]
        values = json.loads(msg.payload.decode("utf-8"))

        telemetry = {
            device_id: [{"ts": int(time.time() * 1000), "values": values}]
        }
        telemetry_json = json.dumps(telemetry)
        
        # Save to buffer database instead of sending directly
        with db_lock:
            c = db_conn.cursor()
            c.execute("INSERT INTO messages (device_id, telemetry_json) VALUES (?, ?)", 
                      (device_id, telemetry_json))
            db_conn.commit()
        logger.info("Buffered message from [%s]", device_id)
            
    except json.JSONDecodeError:
        logger.error("Invalid JSON payload on topic %s: %s", msg.topic, msg.payload)
    except IndexError:
        logger.error("Unexpected topic format: %s", msg.topic)
    except Exception as e:
        logger.error("Failed to buffer message: %s", e)

local_client = mqtt.Client("TinyGateway_Local")
local_client.on_connect = on_local_connect
local_client.on_message = on_message

# --------------------------------------
# Run
# --------------------------------------
try:
    while True:
        try:
            local_client.connect(LOCAL_HOST, LOCAL_PORT, 60)
            break
        except Exception as e:
            logger.error("Could not connect to local broker (%s), retrying...", e)
            time.sleep(5)
            
    local_client.loop_forever()
except KeyboardInterrupt:
    logger.info("Interrupted, shutting down")
finally:
    local_client.disconnect()
    tb_client.loop_stop()
    tb_client.disconnect()
    db_conn.close()
