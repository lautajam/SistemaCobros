bind = "0.0.0.0:5000"

# Un solo worker: los backups automáticos corren en un hilo dentro de la app y
# la restauración bloquea los pedidos con una bandera en memoria; con varios
# procesos se harían backups repetidos. Los threads alcanzan para atender
# pedidos simultáneos (la base de datos ya se encarga de la concurrencia).
workers = 1
threads = 4

# Al apagar el contenedor, gunicorn espera a que terminen los pedidos en curso
# (graceful_timeout) y recién después llama a on_exit, que hace el backup final.
# stop_grace_period en docker-compose.yml debe ser mayor a este valor.
graceful_timeout = 60


def on_exit(server):
    """Se ejecuta en el proceso principal cuando gunicorn ya se está apagando
    (docker compose down / stop, o cerrar Docker Desktop): backup final."""
    try:
        from app import backup

        nombre = backup.backup_al_apagar()
        server.log.info("Backup al apagar creado: %s", nombre)
    except Exception as error:
        server.log.error("No se pudo crear el backup al apagar: %s", error)
