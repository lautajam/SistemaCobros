# syntax=docker/dockerfile:1
# Se fija "bookworm" (Debian 12) a propósito: el .deb de wkhtmltopdf y el
# repositorio de PostgreSQL de más abajo son de esa versión de Debian.
FROM python:3.12-slim-bookworm

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

# Cliente de PostgreSQL 16 (pg_dump / pg_restore) para los backups. Debe ser
# de la misma versión que el servidor (postgres:16 en docker-compose.yml);
# Debian bookworm trae la 15, por eso se usa el repositorio oficial de PostgreSQL.
RUN apt-get update && apt-get install -y --no-install-recommends gnupg \
    && wget -qO- https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p documentos /backups \
    && chown -R appuser:appuser /app /backups
USER appuser

EXPOSE 5000

# Primero se crea/actualiza el esquema de la base de datos (Alembic) y luego
# arranca gunicorn (con exec, para que reciba las señales de apagado de Docker).
# Ver gunicorn.conf.py: un solo worker y backup final al apagar.
CMD ["sh", "-c", "alembic upgrade head && exec gunicorn -c gunicorn.conf.py run:app"]
