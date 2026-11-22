# BioScale - lokal rechnen, Daten bleiben auf dem Rechner.
#   docker build -t bioscale bioscale/
#   docker run --rm -p 8765:8765 -v "$PWD/arbeit:/arbeit" bioscale            # Web-Assistent
#   docker run --rm -v "$PWD/arbeit:/arbeit" bioscale bioscale demo /arbeit/demo
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 MPLBACKEND=Agg
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/bioscale
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[all,test]"
COPY tests ./tests
WORKDIR /arbeit
EXPOSE 8765
CMD ["bioscale", "web", "--host", "0.0.0.0", "--port", "8765", "--arbeitsordner", "/arbeit/web"]
