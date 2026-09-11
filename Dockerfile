FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV RPS_CONFIG_PATH=/config/config.json

CMD ["python", "-m", "receiver_power_sync"]
