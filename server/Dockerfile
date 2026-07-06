FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . .

# Ensure the SSL regeneration script is executable
RUN chmod +x regen-ssl.sh

# Expose the standard port (adjust if server.py uses a different port like 8000 or 443)
EXPOSE 443

# Run your server script
CMD ["python", "server.py"]
