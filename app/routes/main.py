from flask import Blueprint, current_app, render_template

from .. import counters

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    base_dir = current_app.config["BASE_DIR"]
    return render_template(
        "index.html",
        ultimo_boleto=counters.get_last_number(base_dir, "boleto"),
        ultimo_recibo=counters.get_last_number(base_dir, "recibo"),
    )
