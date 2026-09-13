from flask import Blueprint, redirect, url_for, flash

bp = Blueprint("tasacion", __name__, url_prefix="/tasacion")

# Primera versión simple del algoritmo (módulo 11 completo queda pendiente:
# aprender de operaciones reales, tendencias históricas, oferta/demanda de la
# plataforma). Estas constantes las importa routes/tomas.py, que ahora es
# quien corre la Tasación como Paso 3 del flujo unificado "Toma y tasación".
FACTOR_MECANICO = {"Excelente": 1.00, "Bueno": 0.95, "Regular": 0.85, "Malo": 0.70}
FACTOR_ESTETICO = {"Excelente": 1.00, "Bueno": 0.97, "Regular": 0.90, "Malo": 0.80}
MARGEN_OBJETIVO = 0.15  # 15% de ganancia esperada sobre el valor de referencia


@bp.route("/", methods=["GET", "POST"])
def index():
    # La Tasación como pantalla suelta quedó reemplazada por el paso 3 del
    # flujo de Toma y tasación — este blueprint queda solo para no romper
    # links/favoritos viejos.
    flash("La Tasación ahora es el paso 3 del flujo de Toma y tasación — iniciá (o continuá) una toma.", "success")
    return redirect(url_for("tomas.index"))
