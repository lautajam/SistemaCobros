# syntax=docker/dockerfile:1
FROM python:3.12-slim

ARG WKHTMLTOPDF_VERSION=0.12.6.1-3
ARG TARGETARCH

# wkhtmltopdf (build "patched Qt", la misma variante que recomienda el
# README para Windows/Mac) necesita estas librerías del sistema para
# renderizar fuentes, imágenes y páginas correctamente; no vienen en la
# imagen "slim".
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget \
        ca-certificates \
        fontconfig \
        libfreetype6 \
        libjpeg62-turbo \
        libpng16-16 \
        libx11-6 \
        libxcb1 \
        libxext6 \
        libxrender1 \
        xfonts-75dpi \
        xfonts-base \
    && wget -q -O /tmp/wkhtmltox.deb \
        "https://github.com/wkhtmltopdf/packaging/releases/download/${WKHTMLTOPDF_VERSION}/wkhtmltox_${WKHTMLTOPDF_VERSION}.bookworm_${TARGETARCH}.deb" \
    && apt-get install -y --no-install-recommends /tmp/wkhtmltox.deb \
    && rm -f /tmp/wkhtmltox.deb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p data documentos \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

# Un solo worker de Gunicorn: csv_utils.py usa un lock en memoria POR
# PROCESO (ver README, sección "Funcionamiento de los CSV"). Varios workers
# de Gunicorn son procesos separados y no comparten ese lock, lo que podría
# duplicar numeración de boletos/recibos bajo carga concurrente. Los threads
# sí comparten el mismo proceso (y por lo tanto el mismo lock), así que se
# usan varios para no perder capacidad de atender pedidos simultáneos.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "run:app"]
