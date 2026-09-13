from flask import Blueprint, redirect, url_for, flash

bp = Blueprint("inspeccion", __name__, url_prefix="/inspeccion")

# La Inspección visual de chapa ahora es el Paso 2 del flujo unificado
# "Toma y tasación" (ver routes/tomas.py) — este blueprint queda solo para
# no romper links/favoritos viejos.


@bp.route("/")
def index():
    flash("La Inspección visual ahora es el paso 2 del flujo de Toma y tasación.", "success")
    return redirect(url_for("tomas.index"))
