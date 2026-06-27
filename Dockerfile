FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# System deps:
#   build-essential + libpq-dev  → compilar psycopg2
#   libgomp1                     → runtime de OpenMP para XGBoost
#   curl                         → healthcheck del contenedor
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar solo requirements primero para aprovechar la caché de capas:
# si requirements.txt no cambia, pip install se salta en rebuilds.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copiar el resto del código
COPY . .

EXPOSE 8000

# Comando por defecto: API FastAPI.
# Los servicios worker/flower anulan esto con su propia clave `command`
# en docker-compose.yml.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
