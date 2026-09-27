bind = "0.0.0.0:5000"

# Un solo worker: al restaurar un backup la app bloquea los pedidos con una
# bandera en memoria, que solo funciona dentro de un mismo proceso. Los threads
# alcanzan para atender pedidos simultáneos (la base de datos ya se encarga de
# la concurrencia).
workers = 1
threads = 4
