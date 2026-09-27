/*
 * Buscador de clientes reutilizable para los formularios de boleto y recibo.
 * Permite: buscar un cliente existente, seleccionarlo, o crear uno nuevo
 * sin salir del formulario (usando /clientes/api/crear-rapido).
 */
(function () {
    function iniciar(raiz) {
        const input = raiz.querySelector(".input-buscar-cliente");
        const resultados = raiz.querySelector(".resultados-cliente");
        const hiddenId = raiz.querySelector(".hidden-cliente-id");
        const seleccionado = raiz.querySelector(".cliente-seleccionado");
        const botonNuevo = raiz.querySelector(".boton-nuevo-cliente");
        const panelNuevo = raiz.querySelector(".panel-nuevo-cliente");
        let timeoutId = null;

        function mostrarSeleccionado(cliente) {
            hiddenId.value = cliente.id;
            seleccionado.innerHTML =
                "<strong>" + cliente.nombre + "</strong> — " +
                (cliente.dni_cuit || "sin DNI/CUIT") +
                (cliente.telefono ? " · " + cliente.telefono : "") +
                ' &nbsp; <a href="#" class="cambiar-cliente">(cambiar)</a>';
            seleccionado.style.display = "block";
            input.style.display = "none";
            resultados.innerHTML = "";
            resultados.style.display = "none";
            panelNuevo.style.display = "none";
        }

        raiz.addEventListener("click", function (e) {
            if (e.target.classList.contains("cambiar-cliente")) {
                e.preventDefault();
                hiddenId.value = "";
                seleccionado.style.display = "none";
                input.style.display = "block";
                input.value = "";
                input.focus();
            }
        });

        if (input) {
            input.addEventListener("input", function () {
                const q = input.value.trim();
                clearTimeout(timeoutId);
                if (q.length < 1) {
                    resultados.innerHTML = "";
                    resultados.style.display = "none";
                    return;
                }
                timeoutId = setTimeout(function () {
                    fetch("/clientes/api/buscar?q=" + encodeURIComponent(q))
                        .then((r) => r.json())
                        .then((clientes) => {
                            resultados.innerHTML = "";
                            if (clientes.length === 0) {
                                resultados.innerHTML =
                                    '<div class="opcion">Sin resultados. Usá "Nuevo cliente" para crearlo.</div>';
                            } else {
                                clientes.forEach((c) => {
                                    const div = document.createElement("div");
                                    div.className = "opcion";
                                    div.innerHTML =
                                        c.nombre +
                                        "<small>" +
                                        (c.dni_cuit || "") +
                                        (c.telefono ? " · " + c.telefono : "") +
                                        "</small>";
                                    div.addEventListener("click", function () {
                                        mostrarSeleccionado(c);
                                    });
                                    resultados.appendChild(div);
                                });
                            }
                            resultados.style.display = "block";
                        });
                }, 200);
            });
        }

        if (botonNuevo) {
            botonNuevo.addEventListener("click", function () {
                panelNuevo.style.display = panelNuevo.style.display === "none" ? "block" : "none";
            });
        }

        const botonGuardarNuevo = raiz.querySelector(".boton-guardar-nuevo-cliente");
        if (botonGuardarNuevo) {
            botonGuardarNuevo.addEventListener("click", function () {
                const datos = {
                    nombre: raiz.querySelector(".nuevo-cliente-nombre").value.trim(),
                    dni_cuit: raiz.querySelector(".nuevo-cliente-dni").value.trim(),
                    telefono: raiz.querySelector(".nuevo-cliente-telefono").value.trim(),
                    email: raiz.querySelector(".nuevo-cliente-email").value.trim(),
                    direccion: raiz.querySelector(".nuevo-cliente-direccion").value.trim(),
                };
                if (!datos.nombre) {
                    alert("El nombre del cliente es obligatorio.");
                    return;
                }
                fetch("/clientes/api/crear-rapido", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(datos),
                })
                    .then((r) => r.json())
                    .then((cliente) => {
                        if (cliente.error) {
                            alert(cliente.error);
                            return;
                        }
                        mostrarSeleccionado(cliente);
                    });
            });
        }
    }

    document.querySelectorAll(".buscador-cliente").forEach(iniciar);
})();
