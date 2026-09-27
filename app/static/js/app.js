/*
 * Comportamiento general de la interfaz (sin dependencias):
 *  - menú del celular
 *  - avisos (toasts) que se cierran solos
 *  - cuadro de confirmación propio (en vez de confirm(), que algunos
 *    navegadores embebidos no soportan)
 *  - evita enviar dos veces el mismo formulario
 */
(function () {
    "use strict";

    // ---------- Menú del celular ----------
    var boton = document.querySelector("[data-nav-toggle]");
    var nav = document.getElementById("nav");
    if (boton && nav) {
        var iconoAbrir = boton.querySelector("[data-icono-abrir]");
        var iconoCerrar = boton.querySelector("[data-icono-cerrar]");

        var cambiarMenu = function (abrir) {
            nav.classList.toggle("abierto", abrir);
            boton.setAttribute("aria-expanded", abrir ? "true" : "false");
            if (iconoAbrir) { iconoAbrir.hidden = abrir; }
            if (iconoCerrar) { iconoCerrar.hidden = !abrir; }
        };

        boton.addEventListener("click", function () {
            cambiarMenu(!nav.classList.contains("abierto"));
        });
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && nav.classList.contains("abierto")) {
                cambiarMenu(false);
                boton.focus();
            }
        });
        document.addEventListener("click", function (e) {
            if (nav.classList.contains("abierto") && !nav.contains(e.target) && !boton.contains(e.target)) {
                cambiarMenu(false);
            }
        });
        window.matchMedia("(min-width: 900px)").addEventListener("change", function (e) {
            if (e.matches) { cambiarMenu(false); }
        });
    }

    // ---------- Menú de usuario (escritorio) ----------
    var menuUsuario = document.querySelector("[data-menu-usuario]");
    if (menuUsuario) {
        var botonUsuario = menuUsuario.querySelector("[data-usuario-toggle]");
        var panelUsuario = menuUsuario.querySelector("[data-usuario-panel]");
        var cambiarUsuario = function (abrir) {
            panelUsuario.classList.toggle("abierto", abrir);
            botonUsuario.setAttribute("aria-expanded", abrir ? "true" : "false");
        };
        botonUsuario.addEventListener("click", function () {
            cambiarUsuario(!panelUsuario.classList.contains("abierto"));
        });
        document.addEventListener("click", function (e) {
            if (!menuUsuario.contains(e.target)) { cambiarUsuario(false); }
        });
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && panelUsuario.classList.contains("abierto")) {
                cambiarUsuario(false);
                botonUsuario.focus();
            }
        });
    }

    // ---------- Mostrar / ocultar contraseña ----------
    document.querySelectorAll("[data-mostrar-clave]").forEach(function (boton) {
        boton.addEventListener("click", function () {
            var campo = document.getElementById(boton.getAttribute("data-mostrar-clave"));
            if (!campo) { return; }
            var mostrar = campo.type === "password";
            campo.type = mostrar ? "text" : "password";
            boton.querySelector("[data-ojo-cerrado]").hidden = mostrar;
            boton.querySelector("[data-ojo-abierto]").hidden = !mostrar;
        });
    });

    // ---------- Avisos ----------
    document.querySelectorAll("[data-toast]").forEach(function (toast) {
        var cerrar = function () { toast.remove(); };
        var x = toast.querySelector("[data-toast-cerrar]");
        if (x) { x.addEventListener("click", cerrar); }
        // Los errores quedan hasta que se cierran; el resto se va solo.
        if (!toast.classList.contains("error")) { setTimeout(cerrar, 9000); }
    });

    // ---------- Confirmación ----------
    // Uso: <form data-confirm="Mensaje" data-confirm-titulo="Título" data-confirm-boton="Eliminar" data-confirm-tipo="danger">
    var dialogo = document.getElementById("dlg-confirmar");
    var pendiente = null;

    function pedirConfirmacion(form) {
        var titulo = form.getAttribute("data-confirm-titulo") || "¿Confirmar?";
        var mensaje = form.getAttribute("data-confirm");
        var textoBoton = form.getAttribute("data-confirm-boton") || "Confirmar";
        var peligro = form.getAttribute("data-confirm-tipo") !== "primary";

        if (!dialogo || typeof dialogo.showModal !== "function") { return true; }

        dialogo.querySelector("#dlg-titulo").textContent = titulo;
        dialogo.querySelector("#dlg-mensaje").textContent = mensaje;
        var aceptar = dialogo.querySelector("[data-dlg-aceptar]");
        aceptar.textContent = textoBoton;
        aceptar.className = "btn " + (peligro ? "btn-danger" : "btn-primary");
        pendiente = form;
        dialogo.showModal();
        return false;
    }

    if (dialogo) {
        dialogo.querySelector("[data-dlg-cancelar]").addEventListener("click", function () {
            pendiente = null;
            dialogo.close();
        });
        dialogo.querySelector("[data-dlg-aceptar]").addEventListener("click", function () {
            var form = pendiente;
            pendiente = null;
            dialogo.close();
            if (form) {
                form.setAttribute("data-confirmado", "1");
                form.requestSubmit();
            }
        });
        dialogo.addEventListener("cancel", function () { pendiente = null; });
    }

    document.addEventListener("submit", function (e) {
        var form = e.target;
        if (!(form instanceof HTMLFormElement) || e.defaultPrevented) { return; }

        if (form.hasAttribute("data-confirm") && !form.hasAttribute("data-confirmado")) {
            if (!pedirConfirmacion(form)) {
                e.preventDefault();
                return;
            }
        }
        form.removeAttribute("data-confirmado");

        // ---------- Evitar doble envío ----------
        if (form.hasAttribute("data-lock")) {
            var botones = form.querySelectorAll("button[type=submit], input[type=submit]");
            // Se deshabilita después de que el navegador toma los datos del formulario.
            setTimeout(function () {
                botones.forEach(function (b) { b.disabled = true; });
            }, 0);
        }
    });

    // ---------- Selector de archivos propio: muestra el nombre elegido ----------
    document.querySelectorAll("[data-file-input]").forEach(function (input) {
        var nombre = input.closest(".file-picker").querySelector("[data-file-name]");
        input.addEventListener("change", function () {
            nombre.textContent = input.files && input.files.length ? input.files[0].name : "Ningún archivo elegido";
        });
    });

    // Al volver con "atrás" el navegador puede dejar los botones deshabilitados.
    window.addEventListener("pageshow", function () {
        document.querySelectorAll("form[data-lock] button[type=submit]").forEach(function (b) {
            b.disabled = false;
        });
    });
})();
