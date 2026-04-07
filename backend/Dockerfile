# API: FastAPI (uvicorn). Build with context = this directory (see docker-compose.yml service `api`).
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["uvicorn", "fastapi_app.main:app", "--host", "0.0.0.0", "--port", "8080"]
