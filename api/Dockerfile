# Build from the repo root:  docker build -f api/Dockerfile -t rent-api .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    ARTIFACTS_DIR=/app/artifacts \
    FORECASTS_PATH=/app/data/suburb_forecasts.json \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/rentmodel ./rentmodel
COPY api/app ./app
COPY ml/xgb/artifacts ./artifacts
# suburb_forecasts.json is optional; without it projections are disabled with a warning.
COPY web/public/data ./data

RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health')"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
