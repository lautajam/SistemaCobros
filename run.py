"""
Punto de entrada de la aplicación.

Uso normal (Docker, con la base de datos PostgreSQL incluida):
    docker compose up --build

Para abrir la app y probar:
    http://127.0.0.1:5000

Gunicorn carga `app` desde este archivo (ver Dockerfile / gunicorn.conf.py).
Ejecutar `python run.py` directamente solo sirve para desarrollo, con una
base PostgreSQL accesible en la variable de entorno DATABASE_URL.
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
