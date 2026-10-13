# Hugging Face Space: das Studio als einzelner Container (ohne Caddy/Garage).
# Speicher: lokal unter /data. Ohne gebuchten "Persistent Storage" ist /data
# fluechtig -- nach einem Neustart des Space sind hochgeladene Szenen weg.
# Wird von .github/workflows/deploy-hf-space.yml zusammengestellt und gepusht.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        hugin-tools enblend \
    && rm -rf /var/lib/apt/lists/*

# Spaces starten den Container als Benutzer 1000
RUN useradd -m -u 1000 user && mkdir -p /data && chown user /data

WORKDIR /app
COPY platform/app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY platform/app/ /app/
COPY platform/web/ /app/web/
COPY scripts/ /app/scripts/
RUN chown -R user /app

ENV WEB_DIR=/app/web \
    SCRIPTS_DIR=/app/scripts \
    DATA_DIR=/data \
    STORAGE=local

USER user
EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
