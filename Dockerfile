# API: python -m api_server. БД монтируйте в /data (см. docker-compose.yml).
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

ENV PYTHONUNBUFFERED=1
# Китай (Dongchedi): отдельный файл в том же томе /data; можно переопределить при запуске.
ENV WRA_CHINA_DB_PATH=/data/encar_china.db
EXPOSE 8080

CMD ["python", "-m", "api_server", "--host", "0.0.0.0", "--port", "8080", "--db", "/data/encar_cars.db"]
