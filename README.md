# Service Técnico de Computadoras — App de gestión

Aplicación web local (uso en un solo equipo / red interna) para gestionar
la recepción de equipos, boletos, recibos y clientes de un service técnico.
Corre en **Docker** con una base de datos **PostgreSQL**, con **login y roles**
(administrador y técnico) y **backups
completos y manuales**: se crean con un botón, se guardan donde vos elijas en tu
PC (fuera de Docker) y se pueden volver a cargar desde la propia app.

---

## 1. Arquitectura

### Tecnología

- **Backend:** Python + [Flask](https://flask.palletsprojects.com/), servido con Gunicorn.
- **Base de datos:** PostgreSQL 16, con [SQLAlchemy](https://www.sqlalchemy.org/) 2 y migraciones con [Alembic](https://alembic.sqlalchemy.org/) (el esquema se crea y actualiza solo al arrancar).
- **Interfaz:** HTML renderizado por Flask (Jinja2) + **CSS propio** (sistema de diseño responsive, sin frameworks ni compilación) + JavaScript "vanilla". Funciona sin internet.
- **Plantillas de documentos:** HTML + Jinja2, totalmente separadas del código y editables.
- **HTML → PDF:** `pdfkit` + `wkhtmltopdf` (ya instalado dentro de la imagen Docker).
- **Backups:** `pg_dump` / `pg_restore` / `psql` (cliente de PostgreSQL 16, también dentro de la imagen).
- **Login y seguridad:** Flask-Login (sesiones), Flask-WTF (protección CSRF) y contraseñas con hash scrypt.
- **Infraestructura:** Docker Compose con dos servicios (`db` y `app`).

### Servicios y datos en Docker

| Qué | Dónde vive | Visible en tu PC |
|---|---|---|
| Base de datos (clientes, boletos, recibos, configuración, logo, contadores) | volumen de Docker `db_data` | No (por eso existen los backups) |
| PDF generados | carpeta `documentos/` del proyecto | Sí |
| Backups | donde elijas al crearlos (se descargan desde la app) | Sí |

### Estructura de carpetas

```text
service-app/
│
├── Dockerfile                 # Imagen de la app (Python + wkhtmltopdf + cliente PostgreSQL)
├── docker-compose.yml         # Servicios db (PostgreSQL) y app, volúmenes
├── gunicorn.conf.py           # Servidor (un solo worker)
├── alembic.ini
├── .env.example               # Variables opcionales (copiar como .env para usarlas)
├── run.py                     # Punto de entrada (lo carga gunicorn)
├── requirements.txt
│
├── app/                       # Código de la aplicación (Flask)
│   ├── __init__.py            # Application factory y configuración
│   ├── settings.py            # DATABASE_URL leída del entorno
│   ├── db.py                  # Conexión y sesiones de SQLAlchemy
│   ├── models.py              # Tablas de la base + formato de IDs
│   ├── auth.py                # Login, roles y permisos, sesiones, bloqueo de intentos, cabeceras de seguridad, comando reset-admin
│   ├── repo.py                # Acceso a datos (get / listar / insertar / actualizar / eliminar)
│   ├── counters.py            # Numeración correlativa independiente y persistente
│   ├── backup.py              # Crear (para descarga) y restaurar backups
│   ├── pdf_utils.py           # Motor Jinja2 + conversión HTML -> PDF, normalización de nombres
│   ├── documentos.py          # Arma el contexto y guarda cada PDF en su carpeta
│   ├── routes/                # Blueprints (uno por sección de la app)
│   │   ├── main.py            # Pantalla de inicio
│   │   ├── clientes.py        # CRUD de clientes + búsqueda/creación rápida (AJAX)
│   │   ├── boletos.py         # Alta/edición/PDF de boletos
│   │   ├── recibos.py         # Alta/edición/PDF de recibos (standalone o desde un boleto)
│   │   ├── historial.py       # Historial general con pestañas y filtros
│   │   ├── configuracion.py   # Datos del service + logo
│   │   ├── blancos.py         # Boletos/recibos en blanco
│   │   ├── auth.py            # Ingresar / cerrar sesión
│   │   ├── cuenta.py          # Mi cuenta: cambiar contraseña (todos) y datos (admin)
│   │   ├── usuarios.py        # Administración de técnicos (solo admin)
│   │   └── backups.py         # Pantalla de backups: crear (descarga) y restaurar (subir un .zip)
│   ├── templates/             # Plantillas HTML de la INTERFAZ (base.html, _macros.html, _sprite.html + una carpeta por sección)
│   └── static/
│       ├── css/style.css      # Sistema de diseño: variables, componentes, responsive, modo oscuro
│       └── js/                # app.js (menú, avisos, confirmaciones) y clientes.js (buscador de clientes)
│
├── migrations/                # Migraciones de Alembic (esquema de la base)
│
├── templates/                 # ⭐ Plantillas EDITABLES de los documentos PDF
│   ├── boleto.html
│   ├── recibo.html
│   └── README.md              # Variables disponibles en las plantillas
│
└── documentos/                # PDF generados (montada desde tu PC)
    ├── boletos/
    ├── recibos/
    └── blancos/{boletos,recibos}/
```

### Modelo de datos (tablas)

- **clientes:** `id, nombre, dni_cuit, telefono, email, direccion, localidad, codigo_postal, observaciones`
- **boletos:** `id, numero, cliente_id, fecha, hora, equipo, marca, modelo, numero_serie, especificaciones, accesorios, estado_fisico, problema, observaciones`
- **recibos:** `id, numero, cliente_id, boleto_id, fecha, trabajo, descripcion, importe, forma_pago, observaciones`
- **equipos** (auxiliar): `id, cliente_id, tipo, marca, modelo, numero_serie` — se completa solo si el boleto trae N.º de serie, como base para consultar en el futuro el historial de un mismo equipo.
- **configuracion:** una sola fila con los datos del service y el **logo** (guardado en la propia base, así viaja dentro de los backups).
- **contadores:** `tipo, ultimo_numero` con tres filas (`cliente`, `boleto`, `recibo`).
- **usuarios:** `id, usuario, nombre, rol (admin | tecnico), password_hash, activo, debe_cambiar_password, creado, ultimo_ingreso`.
- **sesiones** (sesiones abiertas), **intentos_login** (intentos fallidos) y **ajustes** (claves internas): tablas de seguridad; sus datos no van en los backups.
- `boletos` y `recibos` tienen además `creado_por_id` (el usuario que los creó).

Un boleto **nunca** duplica los datos del cliente: guarda `cliente_id` (clave foránea). Un recibo puede estar asociado a un boleto (`boleto_id`, opcional). Si se elimina un boleto, sus recibos quedan sin boleto asociado.

### Sistema de numeración (`counters.py`)

- La tabla `contadores` guarda el **último número emitido** por tipo, de forma independiente.
- Al crear un boleto/recibo/cliente se incrementa el contador con un único `UPDATE ... RETURNING` (atómico en PostgreSQL, seguro aunque haya pedidos simultáneos) y **recién después** se guarda el registro. El número nunca se calcula como `cantidad + 1`.
- Si se elimina un boleto o recibo, su número queda consumido: el contador no se decrementa.
- IDs resultantes: cliente `C00001`, boleto `B0001` (número visible `0001`), recibo `R0027` (número visible `0027`).

### Plantillas de documentos (`templates/boleto.html`, `templates/recibo.html`)

Son **independientes del código**: se pueden editar con cualquier editor de texto para cambiar diseño, colores, tipografías, textos o campos visibles. Usan sintaxis **Jinja2** (`{{ variable }}`); la lista de variables está en [`templates/README.md`](templates/README.md). Esta carpeta viaja dentro de la imagen de Docker: después de editar una plantilla, reconstruí con `docker compose up --build` para que el cambio se vea en los próximos PDF.

### Generación de PDF (`pdf_utils.py` + `documentos.py`)

1. Se arma un diccionario de contexto (`service`, `cliente`, `boleto`/`recibo`).
2. Se renderiza la plantilla HTML con Jinja2 (el logo se incrusta como imagen dentro del HTML).
3. `wkhtmltopdf` la convierte a PDF (A4, márgenes de impresión).
4. Se guarda en `documentos/boletos`, `documentos/recibos` o `documentos/blancos/...` con el nombre obligatorio:
   - `boleto_recepcion_DD-MM-YYYY_Nombre_Cliente_NNNN.pdf`
   - `recibo_DD-MM-YYYY_Nombre_Cliente_NNNN.pdf`

   El nombre del cliente se normaliza (sin tildes, espacios ni caracteres especiales) solo para el nombre de archivo.
5. Los documentos en blanco usan un nombre fijo (`boleto_recepcion_en_blanco.pdf` / `recibo_en_blanco.pdf`) con sufijo (`_1`, `_2`, ...) si ya existe. No consumen numeración.

### Interfaz (front-end)

Hecha con **CSS propio**, sin frameworks, sin compilar y sin internet. Se adapta a celular, tablet y PC (*mobile-first*).

- **Responsive:** en el celular el menú es una hamburguesa y las tablas se convierten en tarjetas; desde 900 px de ancho aparece la barra de navegación completa. En los formularios del celular, la barra de "Guardar" queda fija abajo.
- **Modo oscuro automático:** sigue la configuración del sistema (`prefers-color-scheme`). Todos los colores están definidos como variables al inicio de `static/css/style.css` (para cambiar la paleta, se editan ahí).
- **Íconos:** SVG incluidos en `templates/_sprite.html`; se usan con `{{ icon("nombre") }}` (macro de `templates/_macros.html`, que también trae `campo`, `area`, `dato` y `archivo` para armar formularios y fichas).
- **Confirmaciones:** los formularios con `data-confirm="mensaje"` (eliminar, restaurar backup) abren un cuadro propio `<dialog>`. No se usan `confirm()`, `prompt()` ni `alert()`: algunos navegadores embebidos (como el integrado de VS Code) no los soportan.
- **Avisos:** los mensajes de Flask (`flash(mensaje, "success" | "error" | "warning")`) se muestran como avisos que se cierran solos.
- **Accesibilidad:** contrastes AA en modo claro y oscuro, foco visible, navegación por teclado en el buscador de clientes y enlace "Ir al contenido".
- Probado en Brave, Edge y un Electron real (como el navegador de VS Code), en 375 px, 768 px y 1366 px de ancho.

### Flujo de navegación

```
Inicio
 ├─ Nuevo boleto -> elegir/crear cliente -> completar equipo -> Guardar -> PDF
 ├─ Nuevo recibo -> elegir/crear cliente -> completar trabajo -> Guardar -> PDF
 ├─ Clientes -> lista/búsqueda -> ficha de cliente -> historial (boletos + recibos)
 ├─ Historial -> pestañas Boletos/Recibos -> buscar/filtrar -> ver/editar/PDF/eliminar
 ├─ Boleto en blanco / Recibo en blanco -> descarga directa de PDF
 ├─ Backups -> crear (se descarga donde elijas) / subir y restaurar
 └─ Configuración -> datos del service + logo
```

Desde el detalle de un boleto se puede tocar **"Crear recibo"**, que abre el formulario de recibo con cliente y boleto ya completados.

---

## 2. Puesta en marcha (Docker)

No hace falta instalar Python, PostgreSQL ni `wkhtmltopdf`: todo viene dentro de las imágenes.

### Requisitos

- **Docker Desktop** (Windows/Mac) o Docker Engine + Compose (Linux).
- En Windows, Docker Desktop necesita **WSL2** y la virtualización activa. Si Docker Desktop dice "virtualization support not detected" aunque la BIOS la tenga activada, abrí PowerShell **como administrador**, corré `wsl --install --no-distribution` y reiniciá la PC.

### Primer arranque

```bash
docker compose up --build
```

La primera vez tarda varios minutos (descarga las imágenes e instala las dependencias). Después abrí:

```
http://127.0.0.1:5000
```

> Los logs dicen `Listening at: http://0.0.0.0:5000`: esa es la dirección interna del contenedor y **no se puede abrir en el navegador** (da `ERR_ADDRESS_INVALID`). Entrá siempre por `127.0.0.1` o `localhost`.

Al iniciar, la app crea sola las tablas de la base (Alembic) y un administrador inicial. Empieza vacía.

**Primer ingreso:** usuario `admin`, contraseña `admin`. El sistema **obliga a cambiar la contraseña** antes de dejarte usar cualquier otra pantalla (y desde *Mi cuenta* podés cambiar también el nombre de usuario).

### Uso de todos los días

| Acción | Cómo |
|---|---|
| Iniciar | Botón ▶ del contenedor en Docker Desktop, o `docker compose up` (o `docker compose up -d` para dejarlo en segundo plano) |
| Abrir la app | En el navegador: `http://127.0.0.1:5000` (conviene guardarlo en favoritos) |
| Detener | `Ctrl+C` en esa terminal, `docker compose stop` / `docker compose down`, o el botón ■ en Docker Desktop |
| Ver los logs | `docker compose logs -f app` |
| Reconstruir tras cambiar código | `docker compose up --build` |

Los contenedores se reinician solos cuando Docker Desktop arranca (`restart: unless-stopped`), así que después de prender la PC alcanza con abrir la dirección en el navegador. La app **no abre el navegador por sí sola**: un contenedor no puede abrir programas de tu PC.

> ⚠️ **`docker compose down -v` BORRA la base de datos** (el flag `-v` elimina el volumen `db_data`). Usá `docker compose down` a secas. Si por error se borra, se recupera restaurando un backup (ver abajo).

### Configuración opcional

Copiá `.env.example` como `.env` y cambiá lo que quieras (contraseña de la base, clave de Flask, zona horaria). Sin `.env` se usan los valores por defecto.

### Uso diario de la app

1. Configurá los datos del service (nombre, CUIT, logo, etc.) en **Configuración**: se completan solos en todos los PDF.
2. **Nuevo boleto** para registrar un equipo que ingresa: buscá el cliente (o creálo sin salir del formulario). Al guardar se genera el PDF.
3. Cuando el trabajo está terminado, abrí el boleto desde **Historial** y tocá **Crear recibo**.
4. Podés imprimir cualquier boleto/recibo desde su pantalla de detalle, o generar formularios en blanco desde el inicio.
5. **Clientes → Ver historial** muestra todos los boletos y recibos de un cliente.

---

## 3. Usuarios, roles y seguridad

No hay pantalla de registro: **nadie puede crear un usuario sin ser administrador**. Todas las páginas exigen iniciar sesión.

### Roles y permisos

| | Administrador | Técnico |
|---|:---:|:---:|
| Clientes: ver / crear | ✅ | ✅ |
| Clientes: editar / eliminar | ✅ | ❌ |
| Boletos y recibos: ver / crear / editar / PDF | ✅ | ✅ |
| Boletos y recibos: eliminar | ✅ | ❌ |
| Historial y formularios en blanco | ✅ | ✅ |
| Usuarios (crear, editar, desactivar y eliminar técnicos) | ✅ | ❌ |
| Cambiar la contraseña de otros usuarios | ✅ | ❌ |
| Cambiar la propia contraseña | ✅ | ✅ |
| Cambiar el propio nombre y usuario | ✅ | ❌ |
| Configuración del service y Backups | ✅ | ❌ |

Los permisos se controlan **en el servidor** (un técnico que escriba a mano la dirección de una pantalla de admin recibe "Sin permiso"); los botones se ocultan solo por comodidad. Cada boleto y recibo guarda quién lo creó ("Creado por").

### Administración de usuarios

- **Usuarios → Nuevo técnico**: nombre, usuario y contraseña inicial (con la opción de obligarlo a cambiarla en su primer ingreso).
- **Contraseña** (de cualquier usuario): el admin define una nueva; se cierran las sesiones abiertas de esa persona.
- **Desactivar**: el técnico no puede ingresar, pero se conserva su historial. **Eliminar** solo se permite si no tiene boletos ni recibos a su nombre.
- No se puede eliminar ni desactivar a un administrador desde la pantalla, así que siempre queda al menos uno. Los administradores adicionales se crean solo por comando (abajo).
- Un cliente solo se puede eliminar si no tiene boletos ni recibos.

### Cómo se protege

- **Contraseñas:** solo se guarda el hash (scrypt); mínimo 8 caracteres; se rechazan las triviales (`12345678`, `password`, igual al usuario...).
- **Sesiones:** cada sesión queda registrada en la base. Cerrar sesión, cambiar la contraseña o desactivar al usuario la invalidan **aunque alguien tenga una copia de la cookie**. Vencen a las 12 horas sin uso.
- **Bloqueo:** 5 intentos fallidos por usuario (o 30 por dirección IP) en 5 minutos bloquean el ingreso temporalmente. Se aplica igual a usuarios que no existen (no se puede averiguar qué usuarios hay) y se guarda en la base.
- **CSRF:** todos los formularios y llamadas de escritura llevan un token.
- **Cabeceras:** política de seguridad de contenido (sin scripts en línea), `X-Frame-Options`, `nosniff`, `Referrer-Policy`, y HSTS cuando hay HTTPS. Las páginas con datos no se guardan en la caché del navegador.
- **Redirecciones:** el parámetro `next` del login solo acepta rutas internas.

### Recuperar el acceso

Si se olvida la contraseña del administrador (o se necesita crear otro admin):

```bash
docker compose exec app flask --app run reset-admin              # usuario "admin"
docker compose exec app flask --app run reset-admin --usuario nombre
```

Pide la contraseña por pantalla (no queda escrita en ningún archivo), crea el admin o le restablece la clave, y cierra sus sesiones.

### Variables de seguridad (`.env`)

| Variable | Para qué |
|---|---|
| `APP_ENV` | `development` (por defecto) o `production`. Con `production`: `SECRET_KEY` obligatoria, cookies solo por HTTPS y **no se crea el admin `admin`/`admin`**. |
| `SECRET_KEY` | Clave que firma las sesiones. En desarrollo, si está vacía, se genera sola y se guarda en la base. |
| `ADMIN_USUARIO`, `ADMIN_PASSWORD` | Admin inicial (solo se usa si todavía no hay usuarios). Con `ADMIN_PASSWORD` no obliga a cambiarla. En producción es la forma de crearlo. |
| `TRUSTED_PROXIES` | `1` si hay un proxy con HTTPS delante (Caddy, nginx...): así la app ve la IP y el `https` reales. |
| `COOKIE_SECURE` | `1`/`0` para forzar el flag `Secure` de la cookie (por defecto: sí en producción). |

Mientras no esté en línea, el puerto de la app se publica solo en `127.0.0.1` (únicamente esta PC puede llegar).

### Puesta en línea (guía para cuando se suba a un VPS)

La app ya está preparada del lado del código; lo que falta es la infraestructura. Pasos recomendados en un VPS con Docker:

1. **No abrir el puerto 5000.** Publicar la app detrás de un proxy con HTTPS automático, por ejemplo [Caddy](https://caddyserver.com/) (`Caddyfile` de una línea: `tu-dominio.com { reverse_proxy app:5000 }`), que obtiene y renueva el certificado solo. Solo el proxy publica los puertos 80 y 443.
2. Definir en `.env`: `APP_ENV=production`, una `SECRET_KEY` larga y aleatoria, `ADMIN_PASSWORD` (una contraseña fuerte, sin usar `admin`), `TRUSTED_PROXIES=1` y cambiar `POSTGRES_PASSWORD`.
3. La base de datos **nunca** se publica fuera de la red interna de Docker (así está hoy).
4. **Backups:** hacerlos seguido y guardarlos **fuera del servidor**. Contienen los hashes de las contraseñas: tratarlos como información sensible.
5. Firewall del servidor: solo 22 (SSH), 80 y 443.

> Esta guía no fue probada todavía con un servidor real. Lo que sí está probado es el comportamiento de la app en modo `production` (arranque, cookies `Secure`, HSTS, IP real detrás del proxy, sin admin por defecto).

---

## 4. Backups

Como la base de datos vive dentro de un volumen de Docker, **los backups son lo que protege tu información**. Son **totalmente manuales**: la app no hace backups por su cuenta, solo cuando vos lo pedís.

### Qué incluye un backup

Un archivo `.zip` con **todo**: la base de datos completa (clientes, boletos, recibos, configuración, logo, numeración y **usuarios con sus contraseñas hasheadas**), los PDF generados y un `manifest.json` (fecha, versión del esquema, cantidades). Las sesiones abiertas no se guardan.

> Como incluye los usuarios, **un backup es información sensible**: guardalo en un lugar seguro.

### Crear un backup

En la pantalla **Backups**, botón **Crear backup**: el backup se arma y se **descarga como un archivo .zip normal del navegador**. No queda ninguna copia dentro de Docker.

Dónde se guarda depende de tu navegador: si tiene activado "Preguntar dónde guardar cada archivo" (en la configuración de descargas) te abre el explorador de archivos; si no, va a la carpeta de descargas. Se probó con Brave, Edge y un navegador tipo Electron (el integrado de VS Code).

> No se usa la función del navegador para "guardar como" (File System Access API) ni `prompt()`/`confirm()`: los navegadores embebidos tipo Electron las exponen pero las bloquean, y dejaban un archivo vacío que después no se podía restaurar.

### Restaurar (incluso en una instalación nueva)

En la pantalla **Backups**, **Subir y restaurar**: elegís un `.zip` de tu PC y se restaura al instante. Si el archivo está vacío (una descarga que no se completó) o no es un backup de esta app, avisa y no toca nada.

**Reemplaza todos los datos actuales** (incluida la numeración, que vuelve al punto del backup, y los **usuarios**) y los PDF. Al terminar, **todos tienen que volver a ingresar** (las sesiones no viajan en los backups); se ingresa con un usuario del backup. No hay backup de seguridad automático: si querés poder volver atrás, creá antes un backup de lo actual. La base se restaura en una sola transacción, así que si el archivo falla, los datos quedan como estaban.

Si el backup es anterior al login (no trae usuarios), se vuelve a crear el administrador inicial. Para una máquina nueva: instalá Docker, `docker compose up --build`, abrí la app, **Backups → Subir y restaurar**, y queda todo cargado. Un backup creado con una versión más nueva de la app se rechaza con un aviso; uno más viejo se restaura y el esquema se actualiza solo.

### Recomendaciones

- **Hacé backups seguido** (por ejemplo al terminar el día) y **guardá copias fuera de la PC** (pendrive, nube): si se rompe o se pierde la PC, se pierde también todo lo que estaba en ella.
- Cerrar la pestaña del navegador o apagar Docker no pierde datos: todo se guarda en la base al instante. Lo que **sí** los borra es `docker compose down -v`.

---

## 5. Notas de diseño y próximos módulos

- El esquema de la base se versiona en `migrations/versions/`. Para cambiar tablas se crea una nueva migración con Alembic (`alembic revision --autogenerate`); se aplica sola en el próximo arranque.
- Gunicorn corre con **un solo worker** (y varios threads): la restauración bloquea los pedidos con una bandera en memoria, que solo funciona dentro de un mismo proceso. La concurrencia de escritura la maneja PostgreSQL.
- Pensada para agregar después, sin romper lo existente: presupuestos, estados de reparación, inventario de repuestos, estadísticas, historial de equipos más completo (ya existe la tabla `equipos`), control de pagos y notificaciones. Cada módulo nuevo es un blueprint en `app/routes/` más sus tablas y migración.
- Pensada para **un solo service, en un equipo o red local**.
