# Build-Kontext ist die Repo-Wurzel (siehe docker-compose.yml), damit die
# bestehenden Pipeline-Skripte aus scripts/ mit ins Image kommen.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        hugin-tools enblend \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY platform/app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY platform/app/ /app/
COPY platform/web/ /app/web/
COPY scripts/e57_extract_images.py scripts/reproject_pano.py scripts/markers_from_xyz.py \
     scripts/pointcloud_web.py scripts/inventory_from_cloud.py /app/scripts/

ENV WEB_DIR=/app/web \
    SCRIPTS_DIR=/app/scripts \
    DATA_DIR=/data

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
