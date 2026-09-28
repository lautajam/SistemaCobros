"""
Tarifario: lista de precios del service.

Cualquier técnico o admin puede verlo y descargarlo en PDF (permiso `tarifario:ver`).
Solo el admin lo edita: alta/edición/baja de trabajos y de sus categorías (permiso
`tarifario:gestionar`). No son documentos emitidos (ningún boleto/recibo los referencia),
así que se editan y eliminan libremente, sin auditoría ni inmutabilidad: el PDF siempre
muestra los precios vigentes.
"""

from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from sqlalchemy import func, select, update

from .. import categorias_trabajo as categorias
from .. import documentos, repo
from ..auth import permiso
from ..db import Session
from ..models import COMPLEJIDADES, CategoriaTrabajo, Trabajo

bp = Blueprint("tarifario", __name__, url_prefix="/tarifario")

VER = "tarifario:ver"
GESTIONAR = "tarifario:gestionar"

CAMPOS = ["nombre", "categoria", "descripcion", "precio", "precio_desde", "complejidad"]


def _validar_trabajo(formulario, categoria_actual=""):
    """Devuelve (error, datos_limpios)."""
    nombre = (formulario.get("nombre") or "").strip()
    descripcion = (formulario.get("descripcion") or "").strip()
    complejidad = (formulario.get("complejidad") or "").strip()
    precio_desde = formulario.get("precio_desde") in ("1", "on", "true")

    if not (2 <= len(nombre) <= 120):
        return "El nombre tiene que tener entre 2 y 120 caracteres.", None
    categoria, error = categorias.validar_categoria(formulario.get("categoria"), categoria_actual)
    if error:
        return error, None
    if not (2 <= len(descripcion) <= 300):
        return "La descripción tiene que tener entre 2 y 300 caracteres.", None
    if complejidad not in COMPLEJIDADES:
        return "Elegí si es un trabajo básico, complejo o avanzado.", None
    try:
        precio = Decimal((formulario.get("precio") or "").strip().replace(",", "."))
        if precio <= 0:
            raise InvalidOperation
    except InvalidOperation:
        return "El precio tiene que ser un número mayor a 0.", None

    return None, {
        "nombre": nombre, "categoria": categoria, "descripcion": descripcion,
        "precio": precio, "precio_desde": precio_desde, "complejidad": complejidad,
    }


def _valores_desde(formulario):
    """Lo que se vuelve a mostrar en el formulario si falla la validación."""
    return {
        "nombre": (formulario.get("nombre") or "").strip(),
        "categoria": (formulario.get("categoria") or "").strip(),
        "descripcion": (formulario.get("descripcion") or "").strip(),
        "precio": (formulario.get("precio") or "").strip(),
        "precio_desde": formulario.get("precio_desde") in ("1", "on", "true"),
        "complejidad": (formulario.get("complejidad") or "").strip(),
    }


def _trabajos_agrupados(q="", categoria="", complejidad=""):
    consulta = select(Trabajo)
    if q:
        consulta = consulta.where(func.lower(Trabajo.nombre).icontains(q.lower(), autoescape=True))
    if categoria:
        consulta = consulta.where(Trabajo.categoria == categoria)
    if complejidad:
        consulta = consulta.where(Trabajo.complejidad == complejidad)
    consulta = consulta.order_by(func.lower(Trabajo.categoria), func.lower(Trabajo.nombre))
    trabajos = [t.to_dict() for t in Session.scalars(consulta)]
    grupos = []
    for trabajo in trabajos:
        if not grupos or grupos[-1]["categoria"] != trabajo["categoria"]:
            grupos.append({"categoria": trabajo["categoria"], "trabajos": []})
        grupos[-1]["trabajos"].append(trabajo)
    return grupos


@bp.route("/")
@permiso(VER)
def lista():
    q = (request.args.get("q") or "").strip()
    categoria = (request.args.get("categoria") or "").strip()
    complejidad = (request.args.get("complejidad") or "").strip()
    grupos = _trabajos_agrupados(q, categoria, complejidad)
    return render_template(
        "tarifario/lista.html", grupos=grupos, q=q, categoria=categoria, complejidad=complejidad,
        categorias=categorias.nombres(), complejidades=COMPLEJIDADES,
    )


@bp.route("/nuevo", methods=["GET", "POST"])
@permiso(GESTIONAR)
def nuevo():
    error, valores = None, {"precio_desde": False}
    if request.method == "POST":
        valores = _valores_desde(request.form)
        error, datos = _validar_trabajo(request.form)
        if not error:
            repo.insertar(Trabajo, datos)
            flash(f"Trabajo «{datos['nombre']}» agregado al tarifario.", "success")
            return redirect(url_for("tarifario.lista"))
    return render_template("tarifario/form.html", trabajo=None, valores=valores, error=error, complejidades=COMPLEJIDADES), (400 if error else 200)


@bp.route("/<int:trabajo_id>/editar", methods=["GET", "POST"])
@permiso(GESTIONAR)
def editar(trabajo_id):
    trabajo = repo.get(Trabajo, trabajo_id)
    if not trabajo:
        abort(404)
    error, valores = None, trabajo
    if request.method == "POST":
        valores = _valores_desde(request.form)
        error, datos = _validar_trabajo(request.form, categoria_actual=trabajo.get("categoria", ""))
        if not error:
            repo.actualizar(Trabajo, trabajo_id, datos)
            flash("Trabajo actualizado.", "success")
            return redirect(url_for("tarifario.lista"))
    return render_template("tarifario/form.html", trabajo=trabajo, valores=valores, error=error, complejidades=COMPLEJIDADES), (400 if error else 200)


@bp.route("/<int:trabajo_id>/eliminar", methods=["POST"])
@permiso(GESTIONAR)
def eliminar(trabajo_id):
    trabajo = repo.get(Trabajo, trabajo_id)
    if not trabajo:
        abort(404)
    repo.eliminar(Trabajo, trabajo_id)
    flash(f"Trabajo «{trabajo['nombre']}» eliminado del tarifario.", "success")
    return redirect(url_for("tarifario.lista"))


@bp.route("/pdf")
@permiso(VER)
def pdf():
    grupos = _trabajos_agrupados()
    try:
        ruta = documentos.generar_pdf_tarifario(grupos)
    except RuntimeError as e:
        flash(str(e), "error")
        return redirect(url_for("tarifario.lista"))
    return send_file(ruta, as_attachment=False)


# ------------------------------------------------------------- categorías

def _validar_nombre_categoria(nombre, ignorar_id=None):
    if not (2 <= len(nombre) <= 60):
        return "El nombre tiene que tener entre 2 y 60 caracteres."
    consulta = select(CategoriaTrabajo).where(func.lower(CategoriaTrabajo.nombre) == nombre.lower())
    if ignorar_id is not None:
        consulta = consulta.where(CategoriaTrabajo.id != ignorar_id)
    if Session.scalar(consulta):
        return "Ya existe una categoría con ese nombre."
    return None


@bp.route("/categorias", methods=["GET", "POST"])
@permiso(GESTIONAR)
def categorias_lista():
    error, nombre_nuevo = None, ""
    if request.method == "POST":
        nombre_nuevo = categorias.normalizar(request.form.get("nombre"))
        error = _validar_nombre_categoria(nombre_nuevo)
        if not error:
            Session.add(CategoriaTrabajo(nombre=nombre_nuevo))
            Session.commit()
            flash(f"Categoría «{nombre_nuevo}» agregada.", "success")
            return redirect(url_for("tarifario.categorias_lista"))
    filas = []
    for cat in Session.scalars(select(CategoriaTrabajo).order_by(func.lower(CategoriaTrabajo.nombre))):
        en_uso = Session.scalar(select(func.count()).select_from(Trabajo).where(Trabajo.categoria == cat.nombre))
        filas.append({"id": cat.id, "nombre": cat.nombre, "en_uso": en_uso})
    return render_template("tarifario/categorias.html", categorias=filas, error=error, nombre_nuevo=nombre_nuevo), (400 if error else 200)


@bp.route("/categorias/<int:categoria_id>/editar", methods=["GET", "POST"])
@permiso(GESTIONAR)
def categoria_editar(categoria_id):
    cat = Session.get(CategoriaTrabajo, categoria_id)
    if cat is None:
        abort(404)
    error, nombre = None, cat.nombre
    if request.method == "POST":
        nombre = categorias.normalizar(request.form.get("nombre"))
        error = _validar_nombre_categoria(nombre, ignorar_id=cat.id)
        if not error:
            viejo = cat.nombre
            if nombre != viejo:
                # Los trabajos no son documentos emitidos: siempre muestran la categoría vigente.
                Session.execute(update(Trabajo).where(Trabajo.categoria == viejo).values(categoria=nombre))
                cat.nombre = nombre
            Session.commit()
            flash("Categoría actualizada.", "success")
            return redirect(url_for("tarifario.categorias_lista"))
    return render_template("tarifario/categoria_form.html", categoria=cat, nombre=nombre, error=error), (400 if error else 200)


@bp.route("/categorias/<int:categoria_id>/eliminar", methods=["POST"])
@permiso(GESTIONAR)
def categoria_eliminar(categoria_id):
    cat = Session.get(CategoriaTrabajo, categoria_id)
    if cat is None:
        abort(404)
    nombre = cat.nombre
    Session.delete(cat)
    Session.commit()
    flash(f"Categoría «{nombre}» eliminada. Los trabajos que la usaban conservan ese nombre.", "success")
    return redirect(url_for("tarifario.categorias_lista"))
