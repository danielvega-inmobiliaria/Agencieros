from flask import Blueprint, render_template

bp = Blueprint("inspeccion", __name__, url_prefix="/inspeccion")

VISTAS = [
    ("frente", "Frente"), ("trasera", "Trasera"), ("lateral_izq", "Lateral izquierdo"),
    ("lateral_der", "Lateral derecho"), ("superior", "Vista superior"),
]


@bp.route("/")
def index():
    # Módulo 5 (schema listo en inspeccion_visual / inspeccion_marcadores).
    # Falta el canvas interactivo para arrastrar marcadores sobre cada vista — ver PROYECTO.md > Pendientes.
    return render_template("inspeccion/index.html", vistas=VISTAS)
