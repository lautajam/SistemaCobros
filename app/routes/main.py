from flask import Blueprint, render_template

from .. import counters

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template(
        "index.html",
        ultimo_boleto=counters.get_last_number("boleto"),
        ultimo_recibo=counters.get_last_number("recibo"),
    )
