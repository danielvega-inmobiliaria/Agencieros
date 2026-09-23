from flask import Blueprint, redirect, url_for, flash

bp = Blueprint("tasacion", __name__, url_prefix="/tasacion")

# Primera versión simple del algoritmo (módulo 11 completo queda pendiente:
# aprender de operaciones reales, tendencias históricas, oferta/demanda de la
# plataforma). Esta constante la importa routes/tomas.py, que ahora es
# quien corre la Tasación como Paso 3 del flujo unificado "Toma y tasación".
#
# Hasta el 22/09/2026 acá también vivían FACTOR_MECANICO/FACTOR_ESTETICO,
# que aplicaban un % de descuento genérico sobre el precio de tabla según
# el Estado mecánico/estético elegido (ej. "Malo" = -20%). Daniel los sacó
# tras un caso real (Renault Kwid con 4 daños marcados, mayormente
# moderados/leves) donde el algoritmo ya había saturado a "Malo" con muy
# poco daño y terminaba descontando el mismo daño DOS veces: una vía el
# costo de reparación ya valorizado punto por punto (Paso 1 y Paso 2), y
# otra vía este factor genérico -- el criterio ahora es que el costo de
# reparación valorizado YA es el descuento por el estado del vehículo, así
# que Estado mecánico/estético quedan como dato informativo (y para
# `riesgo`, en routes/tomas.py) pero no vuelven a tocar el precio.
#
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
