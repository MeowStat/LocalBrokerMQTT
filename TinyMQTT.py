import asyncio
import logging

from hbmqtt.broker import Broker
import threading
import time
import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# === Broker Configuration ===
broker_config = {
    'listeners': {
        'default': {
            'type': 'tcp',
            'bind': '0.0.0.0:1883'
        }
    },
    'sys_interval': 10,
    'auth': {
        'allow-anonymous': True   # <-- Disable anonymous!
        #'plugins': ['auth_file'],   # <-- Use file-based auth
        #'password-file': 'password_file.txt',  # <-- Point to your password file
        #'plugins': ['allow_all_auth']

    },
    'topic-check': {
        'enabled': True,
        'plugins': ['topic_taboo']
    }
}

def start_broker():
    async def broker_coro():
        broker = Broker(broker_config)
        await broker.start()
        logger.info("MQTT Broker started on 0.0.0.0:1883")

    # Each thread needs its own event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(broker_coro())
    loop.run_forever()

# === MQTT Subscriber (in thread) ===
def run_subscriber():
    broker_address = "127.0.0.1"
    topic = "#" #subscribe to all topics

    def on_message(client, userdata, msg):
        # msg.topic = "devices/A4CF125B3C2D/telemetry"
        parts = msg.topic.split("/")
        device_mac = parts[1] if len(parts) > 1 else msg.topic
        logger.info("[%s] topic=%s payload=%s", device_mac, msg.topic, msg.payload.decode("utf-8"))

    def on_subscribe(client, userdata, mid, granted_qos):
        logger.info("Subscribed successfully (mid=%s, qos=%s)", mid, granted_qos)

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info("Subscriber connected to broker")
            client.subscribe(topic, qos=0)
        else:
            logger.error("Subscriber connection failed (rc=%s)", rc)

    client = mqtt.Client("TinyMQTTMonitor")
    client.on_message = on_message
    client.on_subscribe = on_subscribe
    client.on_connect = on_connect

    # Wait a bit for the broker to start
    time.sleep(2)

    try:
        client.connect(broker_address, 1883)
        client.loop_forever()
    except Exception:
        logger.exception("Subscriber encountered an error")

if __name__ == "__main__":
    # Broker in one thread
    try:
        broker_thread = threading.Thread(target=start_broker, daemon=True)
        broker_thread.start()
        logger.info("Broker thread started")
    except Exception:
        logger.exception("Failed to start broker thread")

    # Subscriber in another thread
    try:
        subscriber_thread = threading.Thread(target=run_subscriber, daemon=True)
        subscriber_thread.start()
        logger.info("Subscriber thread started")
    except Exception:
        logger.exception("Failed to start subscriber thread")


    # Keep the main program alive
    while True:
        time.sleep(1)
