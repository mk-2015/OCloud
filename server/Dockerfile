FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    openssl \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN dos2unix regen-ssl.sh && chmod +x regen-ssl.sh

RUN groupadd -r ocuser && useradd -r -g ocuser -d /app -s /sbin/nologin ocuser \
    && mkdir -p /app/data /app/logs \
    && chown -R ocuser:ocuser /app

USER ocuser

EXPOSE 443

CMD ["python", "server.py"]
