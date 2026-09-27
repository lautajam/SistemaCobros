# Plantillas de documentos (`boleto.html` / `recibo.html`)

Estos dos archivos definen **el diseño visual** de los PDF que genera la
aplicación. Podés abrirlos con cualquier editor de texto (Notepad, VS Code,
Sublime, etc.) y modificar libremente:

- HTML (estructura, textos fijos, qué campos se muestran)
- CSS (colores, tipografías, tamaños, márgenes, bordes, espaciados)
- El logo (se inserta automáticamente si lo cargás en Configuración)
- La distribución general del documento

**No hace falta tocar el código Python de la aplicación** para cambiar el
diseño. La aplicación simplemente:

1. Lee el archivo `.html` correspondiente.
2. Reemplaza las variables (`{{ ... }}`) por los datos reales.
3. Convierte el resultado a PDF.
4. Lo guarda en `documentos/boletos/`, `documentos/recibos/` o
   `documentos/blancos/`.

La sintaxis de variables es **Jinja2** (`{{ variable }}`, `{% if %}`, etc.).

## Filtro `blanco`

Todas las plantillas usan un filtro llamado `blanco`, por ejemplo:

```html
{{ cliente.telefono | blanco(15) }}
```

Si `cliente.telefono` tiene un valor, se muestra ese valor. Si está vacío
(por ejemplo, en un documento en blanco), se dibuja una línea de guiones
bajos del largo indicado (`15` caracteres en el ejemplo) para completar a
mano. Podés usarlo en cualquier campo nuevo que agregues.

## Variable `blanco` (booleano)

Además existe una variable booleana `{{ blanco }}` (true/false) que indica
si el documento que se está generando es un "boleto/recibo en blanco". Podés
usarla, por ejemplo, para mostrar u ocultar un aviso:

```html
{% if blanco %}
  <p>Documento en blanco</p>
{% endif %}
```

## Variables de `service` (datos del negocio, sección Configuración)

```text
{{ service.nombre }}
{{ service.cuit }}
{{ service.telefono }}
{{ service.email }}
{{ service.direccion }}
{{ service.localidad }}
{{ service.codigo_postal }}
{{ service.logo_path }}      -> logo incrustado en la página (data URI), o "" si no hay logo cargado
```

## Variables de `cliente`

```text
{{ cliente.id }}
{{ cliente.nombre }}
{{ cliente.dni_cuit }}
{{ cliente.telefono }}
{{ cliente.email }}
{{ cliente.direccion }}
{{ cliente.localidad }}
{{ cliente.codigo_postal }}
{{ cliente.observaciones }}
```

En los documentos en blanco, todos estos campos llegan vacíos.

## Variables de `boleto` (solo disponibles en `boleto.html`)

```text
{{ boleto.id }}
{{ boleto.numero }}
{{ boleto.fecha }}
{{ boleto.hora }}
{{ boleto.equipo }}
{{ boleto.marca }}
{{ boleto.modelo }}
{{ boleto.numero_serie }}
{{ boleto.especificaciones }}
{{ boleto.accesorios }}
{{ boleto.estado_fisico }}
{{ boleto.problema }}
{{ boleto.observaciones }}
```

## Variables de `recibo` (solo disponibles en `recibo.html`)

```text
{{ recibo.id }}
{{ recibo.numero }}
{{ recibo.boleto_id }}       -> vacío si el recibo no está asociado a ningún boleto
{{ recibo.fecha }}
{{ recibo.trabajo }}
{{ recibo.descripcion }}
{{ recibo.importe }}
{{ recibo.forma_pago }}
{{ recibo.observaciones }}
```

## Recomendaciones

- Después de editar una plantilla, generá un PDF de prueba (por ejemplo un
  "Boleto en blanco" desde la pantalla principal) para revisar el resultado.
- El CSS usa `@page { size: A4; margin: 0; }` y un `padding` interno en
  `.hoja`; si cambiás el tamaño de página, ajustá también esos valores.
- Evitá borrar las llaves `{{ }}` de golpe: si necesitás ocultar un campo,
  es más seguro comentar la línea HTML (`<!-- ... -->`) o envolverla en un
  `{% if %}` que borrar la variable, así el resto de la plantilla no se
  desordena.
