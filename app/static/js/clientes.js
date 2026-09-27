/*
 * Buscador de clientes de los formularios de boleto y recibo.
 * Permite buscar un cliente existente, elegirlo, o crear uno nuevo sin salir
 * del formulario (POST /clientes/api/crear-rapido). Todo el texto que viene
 * del servidor se inserta con textContent (nunca como HTML).
 */
(function () {
    "use strict";

    function iniciar(raiz) {
        var q = function (sel) { return raiz.querySelector(sel); };
        var hidden = q(".hidden-cliente-id");
        var cajaSel = q("[data-seleccionado]");
        var cajaBuscar = q("[data-buscar]");
        var input = q("[data-input]");
        var lista = q("[data-resultados]");
        var error = q("[data-error]");
        var panel = q("[data-panel-nuevo]");
        var errorNuevo = q("[data-error-nuevo]");
        var form = raiz.closest("form");

        var temporizador = null;
        var pedidoActual = 0;
        var indice = -1;

        function datosDe(c) {
            return (c.dni_cuit || "sin DNI/CUIT") + (c.telefono ? " · " + c.telefono : "");
        }

        function mostrarError(el, texto) {
            el.textContent = texto;
            el.hidden = !texto;
        }

        function cerrarLista() {
            lista.hidden = true;
            lista.innerHTML = "";
            input.setAttribute("aria-expanded", "false");
            indice = -1;
        }

        function elegir(c) {
            hidden.value = c.id;
            q("[data-sel-nombre]").textContent = c.nombre;
            q("[data-sel-datos]").textContent = datosDe(c);
            q("[data-avatar]").textContent = (c.nombre || "?").charAt(0).toUpperCase();
            cajaSel.hidden = false;
            cajaBuscar.hidden = true;
            panel.hidden = true;
            cerrarLista();
            mostrarError(error, "");
        }

        function cambiar() {
            hidden.value = "";
            cajaSel.hidden = true;
            cajaBuscar.hidden = false;
            input.value = "";
            input.focus();
        }

        function opciones() {
            return lista.querySelectorAll("li[role=option]");
        }

        function marcar(nuevo) {
            var items = opciones();
            if (!items.length) { return; }
            indice = (nuevo + items.length) % items.length;
            items.forEach(function (li, i) {
                li.setAttribute("aria-selected", i === indice ? "true" : "false");
            });
            items[indice].scrollIntoView({ block: "nearest" });
        }

        function dibujar(clientes) {
            lista.innerHTML = "";
            indice = -1;
            if (!clientes.length) {
                var vacio = document.createElement("li");
                vacio.className = "sin-resultados";
                vacio.textContent = "Sin resultados. Podés crear un cliente nuevo.";
                lista.appendChild(vacio);
            } else {
                clientes.forEach(function (c) {
                    var li = document.createElement("li");
                    li.setAttribute("role", "option");
                    li.setAttribute("aria-selected", "false");
                    var nombre = document.createElement("span");
                    nombre.textContent = c.nombre;
                    var detalle = document.createElement("small");
                    detalle.textContent = datosDe(c);
                    li.appendChild(nombre);
                    li.appendChild(detalle);
                    li.addEventListener("mousedown", function (e) {
                        e.preventDefault(); // evita que el input pierda el foco antes de elegir
                        elegir(c);
                    });
                    lista.appendChild(li);
                });
            }
            lista.hidden = false;
            input.setAttribute("aria-expanded", "true");
        }

        function buscar(texto) {
            var numero = ++pedidoActual;
            fetch("/clientes/api/buscar?q=" + encodeURIComponent(texto))
                .then(function (r) {
                    if (!r.ok) { throw new Error("HTTP " + r.status); }
                    return r.json();
                })
                .then(function (clientes) {
                    if (numero !== pedidoActual) { return; } // llegó una respuesta vieja
                    mostrarError(error, "");
                    dibujar(clientes);
                })
                .catch(function () {
                    if (numero !== pedidoActual) { return; }
                    cerrarLista();
                    mostrarError(error, "No se pudo buscar clientes. Reintentá en un momento.");
                });
        }

        input.addEventListener("input", function () {
            var texto = input.value.trim();
            clearTimeout(temporizador);
            if (!texto) { pedidoActual++; cerrarLista(); return; }
            temporizador = setTimeout(function () { buscar(texto); }, 200);
        });

        input.addEventListener("keydown", function (e) {
            if (e.key === "ArrowDown") { e.preventDefault(); marcar(indice + 1); }
            else if (e.key === "ArrowUp") { e.preventDefault(); marcar(indice - 1); }
            else if (e.key === "Escape") { cerrarLista(); }
            else if (e.key === "Enter") {
                e.preventDefault(); // Enter en el buscador no envía el formulario
                var items = opciones();
                if (items.length) { items[indice >= 0 ? indice : 0].dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true })); }
            }
        });

        input.addEventListener("blur", function () { setTimeout(cerrarLista, 120); });

        q("[data-cambiar]").addEventListener("click", cambiar);

        q("[data-nuevo]").addEventListener("click", function () {
            panel.hidden = !panel.hidden;
            if (!panel.hidden) { q("[data-nuevo-nombre]").focus(); }
        });

        q("[data-cancelar-nuevo]").addEventListener("click", function () {
            panel.hidden = true;
            mostrarError(errorNuevo, "");
        });

        q("[data-guardar-nuevo]").addEventListener("click", function () {
            var boton = this;
            var datos = {
                nombre: q("[data-nuevo-nombre]").value.trim(),
                dni_cuit: q("[data-nuevo-dni]").value.trim(),
                telefono: q("[data-nuevo-telefono]").value.trim(),
                email: q("[data-nuevo-email]").value.trim()
            };
            if (!datos.nombre) {
                mostrarError(errorNuevo, "El nombre es obligatorio.");
                q("[data-nuevo-nombre]").focus();
                return;
            }
            boton.disabled = true;
            fetch("/clientes/api/crear-rapido", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(datos)
            })
                .then(function (r) { return r.json().then(function (cuerpo) { return { ok: r.ok, cuerpo: cuerpo }; }); })
                .then(function (res) {
                    if (!res.ok || res.cuerpo.error) {
                        mostrarError(errorNuevo, res.cuerpo.error || "No se pudo guardar el cliente.");
                        return;
                    }
                    mostrarError(errorNuevo, "");
                    elegir(res.cuerpo);
                })
                .catch(function () { mostrarError(errorNuevo, "No se pudo guardar el cliente. Reintentá."); })
                .then(function () { boton.disabled = false; });
        });

        // No dejar guardar el boleto/recibo sin cliente.
        if (form) {
            form.addEventListener("submit", function (e) {
                if (!hidden.value) {
                    e.preventDefault();
                    mostrarError(error, "Elegí un cliente o creá uno nuevo antes de guardar.");
                    (cajaBuscar.hidden ? q("[data-cambiar]") : input).scrollIntoView({ block: "center", behavior: "smooth" });
                    if (!cajaBuscar.hidden) { input.focus(); }
                }
            });
        }
    }

    document.querySelectorAll("[data-buscador]").forEach(iniciar);
})();
