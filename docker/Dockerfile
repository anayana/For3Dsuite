# For3Dsuite -- CPU-Pipeline + Viewer (Inventur, RGB-Analyse, Wuchsmodell-Export,
# Gallery/Studio). Kein GPU noetig. Das 3DGS-Training laeuft separat, siehe
# docker/Dockerfile.gpu bzw. scripts/train_runpod.sh (RunPod).
FROM python:3.11-slim

# opencv-python-headless braucht libglib; git/curl fuer optionale Schritte
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY docker/requirements.txt docker/requirements.txt
RUN pip install --no-cache-dir -r docker/requirements.txt

COPY . .

EXPOSE 8000
ENTRYPOINT ["bash", "docker/entrypoint.sh"]
CMD ["serve"]
