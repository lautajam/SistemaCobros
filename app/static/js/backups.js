/*
 * Pantalla de backups. El backup se descarga como un archivo normal. La
 * respuesta trae una cookie con la misma "marca" enviada en el formulario: al
 * verla, sabemos que la descarga empezó y volvemos a habilitar el botón.
 */
(function () {
    "use strict";

    var form = document.querySelector("[data-backup-crear]");
    if (!form) { return; }

    form.addEventListener("submit", function () {
        var marca = String(Date.now());
        form.marca.value = marca;
        var boton = document.getElementById("btn-crear");
        var texto = boton.querySelector("[data-texto]");
        var textoOriginal = texto.textContent;
        boton.disabled = true;
        texto.textContent = "Creando backup…";

        var restaurar = function () {
            clearInterval(espera);
            clearTimeout(limite);
            document.cookie = "backup_listo=; Max-Age=0; path=/backups";
            boton.disabled = false;
            texto.textContent = textoOriginal;
        };
        var espera = setInterval(function () {
            if (document.cookie.indexOf("backup_listo=" + marca) !== -1) { restaurar(); }
        }, 300);
        var limite = setTimeout(restaurar, 180000);
    });
})();
