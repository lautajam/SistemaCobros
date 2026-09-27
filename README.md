# Service Técnico de Computadoras — App de gestión

Aplicación web local (uso en un solo equipo / red interna) para gestionar
la recepción de equipos, boletos, recibos y clientes de un service técnico.
**Toda la información persistente se guarda en archivos CSV**, sin ninguna
base de datos SQL/NoSQL.

---

## 1. Arquitectura

### Tecnología elegida

- **Backend:** Python + [Flask](https://flask.palletsprojects.com/) (micro-framework, sin ORM).
- **Interfaz:** HTML renderizado por el propio Flask (Jinja2) + CSS simple, sin frameworks de JS pesados. Un poco de JavaScript "vanilla" para la búsqueda de clientes en vivo.
- **Persistencia:** archivos **CSV** (módulo estándar `csv` de Python), UTF-8, con escritura atómica.
- **Plantillas de documentos:** HTML + Jinja2, totalmente separadas del código.
- **HTML → PDF:** [`pdfkit`](https://pypi.org/project/pdfkit/) + `wkhtmltopdf` (motor de renderizado que respeta bien CSS, márgenes, tablas y saltos de página; pensado para impresión).

**¿Por qué esta combinación?**
Flask es liviano, no impone una base de datos (a diferencia de Django) y es
perfecto para una app CRUD simple que corre en un solo equipo. Al ser una
app web local, no depende del sistema operativo para la interfaz (Windows,
Linux o Mac: se abre en el navegador). `wkhtmltopdf` es el motor más simple
y confiable para convertir HTML/CSS a PDF con buena fidelidad de impresión,
sin depender de librerías nativas pesadas.

### Estructura de carpetas

```text
service-app/
│
├── run.py                     # Punto de entrada (python run.py)
├── requirements.txt
│
├── app/                       # Código de la aplicación (Flask)
│   ├── __init__.py            # Application factory, configuración, inicialización de storage
│   ├── csv_utils.py           # Lectura/escritura atómica y segura de CSV
│   ├── counters.py            # Numeración correlativa independiente y persistente
│   ├── models.py              # Definición de columnas de cada CSV + formato de IDs
│   ├── pdf_utils.py           # Motor Jinja2 + conversión HTML -> PDF, normalización de nombres
│   ├── documentos.py          # Reglas de negocio: arma el contexto y guarda cada PDF en su carpeta
│   ├── routes/                # Blueprints (uno por sección de la app)
│   │   ├── main.py            # Pantalla de inicio
│   │   ├── clientes.py        # CRUD de clientes + búsqueda/creación rápida (AJAX)
│   │   ├── boletos.py         # Alta/edición/PDF de boletos
│   │   ├── recibos.py         # Alta/edición/PDF de recibos (standalone o desde un boleto)
│   │   ├── historial.py       # Historial general con pestañas y filtros
│   │   ├── configuracion.py   # Datos del service + logo
│   │   └── blancos.py         # Generación de boletos/recibos en blanco
│   ├── templates/             # Plantillas HTML de la INTERFAZ (no confundir con las de documentos)
│   └── static/                # CSS y JS de la interfaz
│
├── templates/                 # ⭐ Plantillas EDITABLES de los documentos PDF
│   ├── boleto.html
│   ├── recibo.html
│   └── README.md              # Documentación de todas las variables disponibles
│
├── data/                      # Persistencia (se crea sola en el primer arranque)
│   ├── clientes/clientes.csv
│   ├── boletos/boletos.csv
│   ├── recibos/recibos.csv
│   ├── equipos/equipos.csv
│   └── configuracion/
│       ├── configuracion.csv
│       └── contadores.csv
│
└── documentos/                # PDF generados (se crea solo en el primer arranque)
    ├── boletos/
    ├── recibos/
    └── blancos/
        ├── boletos/
        └── recibos/
```

### Modelo de datos (columnas de cada CSV)

- **clientes.csv:** `id, nombre, dni_cuit, telefono, email, direccion, localidad, codigo_postal, observaciones`
- **boletos.csv:** `id, numero, cliente_id, fecha, hora, equipo, marca, modelo, numero_serie, especificaciones, accesorios, estado_fisico, problema, observaciones`
- **recibos.csv:** `id, numero, cliente_id, boleto_id, fecha, trabajo, descripcion, importe, forma_pago, observaciones`
- **equipos.csv** (auxiliar, opcional): `id, cliente_id, tipo, marca, modelo, numero_serie` — se completa solo si el boleto trae N.º de serie, para poder consultar en el futuro el historial de un mismo equipo sin complicar la v1.
- **configuracion.csv:** una sola fila con los datos del service (`nombre, cuit, telefono, email, direccion, localidad, codigo_postal, logo`).
- **contadores.csv:** `tipo, ultimo_numero` con tres filas (`cliente`, `boleto`, `recibo`).

Un boleto **nunca** duplica los datos del cliente: guarda `cliente_id` y la
app hace el "join" en memoria al mostrar o generar el PDF. Lo mismo para
`boleto_id` en un recibo (puede estar vacío).

### Funcionamiento de los CSV (`csv_utils.py`)

- Se crean automáticamente (carpeta + archivo + encabezado) la primera vez que se necesitan.
- Toda escritura reescribe el archivo completo en un **archivo temporal** y luego lo reemplaza con `os.replace()` (operación atómica a nivel de sistema de archivos), para que nunca quede un CSV a medio escribir.
- Se usa el módulo `csv` estándar (`QUOTE_MINIMAL`), que escapa automáticamente comas, comillas y saltos de línea dentro de un campo.
- Un lock en memoria por archivo evita condiciones de carrera si el servidor atiende dos pedidos al mismo tiempo.

### Sistema de numeración (`counters.py`)

- `contadores.csv` guarda el **último número emitido** por tipo de documento (`cliente`, `boleto`, `recibo`), completamente independientes entre sí.
- Al crear un boleto/recibo/cliente: se lee el contador, se incrementa, se guarda inmediatamente y **recién después** se guarda el registro. El número nunca se calcula como `len(registros) + 1`.
- Si se elimina un boleto o recibo, su número queda consumido para siempre: el contador no se decrementa ni se reutiliza.
- IDs resultantes: cliente `C00001`, boleto `B0001` (número visible `0001`), recibo `R0027` (número visible `0027`).

### Sistema de plantillas HTML (`templates/boleto.html`, `templates/recibo.html`)

Estas plantillas son **independientes del código** de la aplicación: se
pueden editar con cualquier editor de texto para cambiar diseño, colores,
tipografías, logo, textos o campos visibles. Usan sintaxis **Jinja2**
(`{{ variable }}`). Toda la lista de variables disponibles está documentada
en [`templates/README.md`](templates/README.md).

### Sistema de generación de PDF (`pdf_utils.py` + `documentos.py`)

1. Se arma un diccionario de contexto (`service`, `cliente`, `boleto`/`recibo`).
2. Se renderiza la plantilla HTML correspondiente con Jinja2.
3. Se convierte el HTML resultante a PDF con `wkhtmltopdf` (vía `pdfkit`), con opciones pensadas para impresión (tamaño A4, márgenes, acceso a archivos locales para el logo).
4. Se guarda en la carpeta que corresponde (`documentos/boletos`, `documentos/recibos` o `documentos/blancos/...`) con el nombre de archivo obligatorio:
   - `boleto_recepcion_DD-MM-YYYY_Nombre_Cliente_NNNN.pdf`
   - `recibo_DD-MM-YYYY_Nombre_Cliente_NNNN.pdf`
   El nombre del cliente se normaliza (sin tildes, sin espacios, sin caracteres especiales) solo para el nombre de archivo; en `clientes.csv` el nombre queda intacto.
5. Los documentos en blanco usan un nombre fijo (`boleto_recepcion_en_blanco.pdf` / `recibo_en_blanco.pdf`) y, si ya existe un archivo con ese nombre, se agrega un sufijo (`_1`, `_2`, ...) para no pisarlo. No consumen numeración.

### Flujo de navegación

```
Inicio
 ├─ Nuevo boleto -> elegir/crear cliente -> completar equipo -> Guardar -> PDF
 ├─ Nuevo recibo -> elegir/crear cliente -> completar trabajo -> Guardar -> PDF
 ├─ Clientes -> lista/búsqueda -> ficha de cliente -> historial (boletos + recibos)
 ├─ Historial -> pestañas Boletos/Recibos -> buscar/filtrar -> ver/editar/PDF/eliminar
 ├─ Boleto en blanco / Recibo en blanco -> descarga directa de PDF
 └─ Configuración -> datos del service + logo
```

Desde el detalle de un boleto se puede tocar **"Crear recibo"**, que abre el
formulario de recibo con cliente y referencia al boleto ya completados; el
usuario solo carga trabajo realizado, importe y forma de pago. También se
puede crear un recibo totalmente independiente desde "Nuevo recibo".

---

## 2. Instalación y puesta en marcha

### Requisitos

- Python 3.9 o superior.
- El programa **wkhtmltopdf** instalado en el sistema. **Importante:** `pip install pdfkit` (paso siguiente) NO alcanza — `pdfkit` es solo un conector en Python hacia el programa real `wkhtmltopdf`, que hay que instalar aparte:
  - **Windows:** descargar el instalador `.exe` desde <https://wkhtmltopdf.org/downloads.html> (la versión para Windows 64-bit), ejecutarlo con las opciones por defecto, y **cerrar y volver a abrir la terminal** (o reiniciar el equipo) antes de correr la app, para que Windows reconozca el nuevo programa.
  - **macOS:** descargarlo de la misma página, o `brew install wkhtmltopdf` si usás Homebrew.
  - **Debian/Ubuntu:** `sudo apt-get install wkhtmltopdf`
  - **Fedora:** `sudo dnf install wkhtmltopdf`

  Si después de instalarlo la app sigue sin encontrarlo (error `No wkhtmltopdf executable found`), definí la ruta manualmente antes de ejecutar `run.py`. En Windows (símbolo del sistema):
  ```cmd
  set WKHTMLTOPDF_PATH=C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe
  python run.py
  ```
  (la ruta exacta depende de dónde haya quedado instalado; normalmente es esa).

  Mientras `wkhtmltopdf` no esté disponible, la aplicación sigue funcionando con normalidad — guarda igual los clientes, boletos y recibos en los CSV — y solo muestra un aviso explicando cómo instalarlo cuando intenta generar un PDF, en vez de romperse.

### Instalación

```bash
cd service-app
python -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Ejecutar la aplicación

```bash
python run.py
```

Luego abrí en el navegador:

```
http://127.0.0.1:5000
```

La primera vez que se ejecuta, la aplicación crea automáticamente todas las
carpetas y archivos CSV necesarios dentro de `data/` y `documentos/`. No hace
falta ninguna configuración adicional ni instalar una base de datos.

### Uso diario

1. Configurá los datos del service (nombre, CUIT, logo, etc.) en **Configuración** — se completan solos en todos los PDF.
2. Usá **Nuevo boleto** para registrar un equipo que ingresa: buscá el cliente (o creálo sin salir del formulario) y completá los datos del equipo. Al guardar se genera el PDF automáticamente.
3. Cuando el trabajo está terminado, abrí el boleto correspondiente desde **Historial** y tocá **Crear recibo**.
4. Podés imprimir cualquier boleto/recibo desde su pantalla de detalle ("Ver / Imprimir PDF"), o generar formularios en blanco para completar a mano desde la pantalla de inicio.
5. **Clientes → Ver historial** muestra todos los boletos y recibos de un cliente en un solo lugar.

---

## 3. Notas de diseño y próximos módulos

Pensada para agregar después, sin romper lo existente: presupuestos, estados
de reparación, inventario de repuestos, estadísticas, historial de equipos
más completo (ya existe `equipos.csv` como base), control de pagos y
notificaciones. La separación en blueprints (`app/routes/`) y la capa de
acceso a CSV (`csv_utils.py`) están pensadas para que un módulo nuevo no
tenga que tocar los existentes.

Esta aplicación está pensada para uso de **un solo service, en un equipo o
red local** (no para múltiples instancias escribiendo a la vez sobre los
mismos archivos CSV de una carpeta compartida por red, ya que el mecanismo
de locking es en memoria, dentro de un mismo proceso).
