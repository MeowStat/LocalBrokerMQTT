FROM python:3.8.5-slim

# Set working directory
WORKDIR /app

# Copy dependency list and install them
COPY requirements_docker.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements_docker.txt

# Copy source code
COPY . .

# Default command (can be overridden by docker-compose)
CMD ["python3", "TinyMQTT.py"]
