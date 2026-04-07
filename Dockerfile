# API: FastAPI (uvicorn). Docker Compose: см. docker-compose.yml и .env.example.
# Легаси-сервер: docker run ... python -m api_server --host 0.0.0.0 --port 8080 --db /data/encar_cars.db
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["uvicorn", "fastapi_app.main:app", "--host", "0.0.0.0", "--port", "8080"]
