from flask import Blueprint, render_template

from database import query

bp = Blueprint("finanzas", __name__, url_prefix="/finanzas")


@bp.route("/")
def index():
    ganancia_mensual = query(
        """SELECT strftime('%Y-%m', fecha_venta) mes,
                  SUM(valor_vendido - valor_compra - gastos) ganancia,
                  COUNT(*) unidades
           FROM vehiculos
           WHERE estado = 'vendido' AND fecha_venta IS NOT NULL
           GROUP BY mes ORDER BY mes DESC LIMIT 12"""
    )
    ganancia_anual = query(
        """SELECT strftime('%Y', fecha_venta) anio,
                  SUM(valor_vendido - valor_compra - gastos) ganancia
           FROM vehiculos
           WHERE estado = 'vendido' AND fecha_venta IS NOT NULL
           GROUP BY anio ORDER BY anio DESC"""
    )
    capital_invertido = query(
        """SELECT COALESCE(SUM(valor_compra + gastos), 0) total FROM vehiculos
           WHERE estado != 'vendido'""",
        one=True,
    )["total"]
    capital_inmovilizado = query(
        """SELECT COALESCE(SUM(valor_compra + gastos), 0) total FROM vehiculos
           WHERE estado IN ('en_reparacion', 'por_ingresar')""",
        one=True,
    )["total"]
    ranking = query(
        """SELECT marca, modelo, version, anio, valor_compra, gastos, valor_vendido,
                  (valor_vendido - valor_compra - gastos) ganancia,
                  CASE WHEN (valor_compra + gastos) > 0
                       THEN ROUND((valor_vendido - valor_compra - gastos) * 100.0 / (valor_compra + gastos), 1)
                       ELSE 0 END rentabilidad_pct
           FROM vehiculos
           WHERE estado = 'vendido' AND valor_vendido IS NOT NULL
           ORDER BY rentabilidad_pct DESC"""
    )
    return render_template(
        "finanzas/index.html",
        ganancia_mensual=ganancia_mensual,
        ganancia_anual=ganancia_anual,
        capital_invertido=capital_invertido,
        capital_inmovilizado=capital_inmovilizado,
        ranking=ranking,
    )
