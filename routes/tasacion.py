from flask import Blueprint, render_template, request

from database import execute

bp = Blueprint("tasacion", __name__, url_prefix="/tasacion")

# Primera versión simple del algoritmo (módulo 11 completo queda pendiente:
# aprender de operaciones reales, tendencias históricas, oferta/demanda de la plataforma).
FACTOR_MECANICO = {"Excelente": 1.00, "Bueno": 0.95, "Regular": 0.85, "Malo": 0.70}
FACTOR_ESTETICO = {"Excelente": 1.00, "Bueno": 0.97, "Regular": 0.90, "Malo": 0.80}
MARGEN_OBJETIVO = 0.15  # 15% de ganancia esperada sobre el valor de referencia


@bp.route("/", methods=["GET", "POST"])
def index():
    resultado = None
    if request.method == "POST":
        f = request.form
        valor_referencia = float(f.get("valor_referencia") or 0)
        estado_mecanico = f.get("estado_mecanico", "Bueno")
        estado_estetico = f.get("estado_estetico", "Bueno")
        gastos_estimados = float(f.get("gastos_estimados") or 0)

        factor = FACTOR_MECANICO[estado_mecanico] * FACTOR_ESTETICO[estado_estetico]
        valor_ajustado = valor_referencia * factor
        precio_max_recomendado = valor_ajustado - gastos_estimados - (valor_referencia * MARGEN_OBJETIVO)
        margen_esperado = valor_ajustado - precio_max_recomendado - gastos_estimados

        malos = [estado_mecanico, estado_estetico].count("Malo")
        regulares = [estado_mecanico, estado_estetico].count("Regular")
        if malos >= 1 or gastos_estimados > valor_referencia * 0.25:
            riesgo = "Alto"
        elif regulares >= 1:
            riesgo = "Medio"
        else:
            riesgo = "Bajo"

        resultado = {
            "precio_max_recomendado": round(precio_max_recomendado),
            "riesgo": riesgo,
            "margen_esperado": round(margen_esperado),
        }

        execute(
            """INSERT INTO tasaciones
               (marca, modelo, version, anio, valor_referencia, estado_mecanico, estado_estetico,
                gastos_estimados, precio_max_recomendado, riesgo, margen_esperado)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                f.get("marca"), f.get("modelo"), f.get("version"), f.get("anio") or None,
                valor_referencia, estado_mecanico, estado_estetico, gastos_estimados,
                resultado["precio_max_recomendado"], riesgo, resultado["margen_esperado"],
            ),
        )

    return render_template(
        "tasacion/index.html",
        resultado=resultado,
        opciones=["Excelente", "Bueno", "Regular", "Malo"],
        form=request.form,
    )
