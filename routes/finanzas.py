from flask import Blueprint, render_template, session

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
    # Una seña retenida es ganancia (Daniel 19/09/2026): entra completa en el
    # mes/año en que se decidió retenerla, sin sumar unidades vendidas.
    # Financiación todavía no guarda agencia_id al crear un plan: NULL = agencia 1.
    agencia_id = session["agencia_id"]
    retenidas = query(
        """SELECT f AS fecha, SUM(m) total FROM (
               SELECT sena AS m, sena_resolucion_fecha AS f FROM ventas
               WHERE sena_resolucion = 'retenida' AND COALESCE(agencia_id, 1) = ?
               UNION ALL
               SELECT anticipo AS m, sena_resolucion_fecha AS f FROM financiaciones
               WHERE sena_resolucion = 'retenida' AND COALESCE(agencia_id, 1) = ?)
           WHERE f IS NOT NULL GROUP BY f""",
        (agencia_id, agencia_id),
    )
    por_mes = {
        g["mes"]: {"mes": g["mes"], "unidades": g["unidades"], "ganancia": g["ganancia"] or 0, "senas": 0}
        for g in ganancia_mensual
    }
    por_anio = {
        g["anio"]: {"anio": g["anio"], "ganancia": g["ganancia"] or 0, "senas": 0} for g in ganancia_anual
    }
    for r in retenidas:
        mes, anio = r["fecha"][:7], r["fecha"][:4]
        m = por_mes.setdefault(mes, {"mes": mes, "unidades": 0, "ganancia": 0, "senas": 0})
        m["ganancia"] += r["total"] or 0
        m["senas"] += r["total"] or 0
        a = por_anio.setdefault(anio, {"anio": anio, "ganancia": 0, "senas": 0})
        a["ganancia"] += r["total"] or 0
        a["senas"] += r["total"] or 0
    ganancia_mensual = sorted(por_mes.values(), key=lambda g: g["mes"], reverse=True)[:12]
    ganancia_anual = sorted(por_anio.values(), key=lambda g: g["anio"], reverse=True)
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
