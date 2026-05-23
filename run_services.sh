#!/bin/bash

# run_services.sh
# Script to run TinyMQTT.py and TinyGateway.py concurrently.

echo "Starting TinyMQTT.py..."
python3 TinyMQTT.py &
MQTT_PID=$!

# Optional delay to ensure MQTT broker starts before Gateway
sleep 2

echo "Starting TinyGateway.py..."
python3 TinyGateway.py &
GATEWAY_PID=$!

echo "--------------------------------------------------------"
echo "Services are running in the background."
echo "TinyMQTT PID: $MQTT_PID"
echo "TinyGateway PID: $GATEWAY_PID"
echo "Press Ctrl+C to stop both services."
echo "--------------------------------------------------------"

# Handle Ctrl+C (SIGINT) and kill both child processes
trap "echo -e '\nStopping services...'; kill $MQTT_PID $GATEWAY_PID 2>/dev/null; echo 'Done.'; exit 0" SIGINT SIGTERM

# Wait for background processes to finish (or for user to press Ctrl+C)
wait $MQTT_PID
wait $GATEWAY_PID
