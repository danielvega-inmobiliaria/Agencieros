from flask import Blueprint, redirect, url_for, flash

bp = Blueprint("tasacion", __name__, url_prefix="/tasacion")

# Primera versión simple del algoritmo (módulo 11 completo queda pendiente:
# aprender de operaciones reales, tendencias históricas, oferta/demanda de la
# plataforma). Estas constantes las importa routes/tomas.py, que ahora es
# quien corre la Tasación como Paso 3 del flujo unificado "Toma y tasación".
FACTOR_MECANICO = {"Excelente": 1.00, "Bueno": 0.95, "Regular": 0.85, "Malo": 0.70}
FACTOR_ESTETICO = {"Excelente": 1.00, "Bueno": 0.97, "Regular": 0.90, "Malo": 0.80}
# % de ganancia esperada sobre el valor de referencia -- hasta el
# 21/09/2026 era un valor fijo para todas las tasaciones de todas las
# agencias. Ahora es solo el DEFAULT: cada agencia puede configurar el
# suyo en Admin (`agencia_config.margen_objetivo_pct`) y además se puede
# pisar por toma puntual, evaluando ese negocio en particular (ver
# `_margen_objetivo_para` en routes/tomas.py).
MARGEN_OBJETIVO_DEFAULT = 0.15


@bp.route("/", methods=["GET", "POST"])
def index():
    # La Tasación como pantalla suelta quedó reemplazada por el paso 3 del
    # flujo de Toma y tasación — este blueprint queda solo para no romper
    # links/favoritos viejos.
    flash("La Tasación ahora es el paso 3 del flujo de Toma y tasación — iniciá (o continuá) una toma.", "success")
    return redirect(url_for("tomas.index"))
