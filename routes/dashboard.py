from flask import Blueprint, render_template

from database import query
from routes.mensajes import contar_no_leidos

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

# Reutiliza los mismos colores que ya usan los badges en toda la app
# (Stock/Financiación), para que los gráficos del dashboard no introduzcan
# una paleta nueva — así Daniel ya sabe qué significa cada color.
COLOR_DISPONIBLE = "var(--green)"
COLOR_POR_INGRESAR = "var(--gold-light)"
COLOR_EN_REPARACION = "var(--red)"
COLOR_COBRADO = "var(--green)"
COLOR_ADEUDADO = "var(--red)"


def _grafico_torta(segmentos):
    """Arma, a partir de una lista de {label, value, color}, los datos
    listos para dibujar una torta con conic-gradient puro en CSS (sin
    librerías externas — la app tiene que poder correr sin internet en una
    red local). Devuelve los segmentos con su % ya calculado y el string de
    stops para el conic-gradient (con los cortes acumulados)."""
    total = sum(s["value"] for s in segmentos)
    stops = []
    acumulado = 0.0
    resultado = []
    for s in segmentos:
        pct = round((s["value"] / total) * 100, 1) if total else 0
        inicio = acumulado
        acumulado += pct
        if s["value"]:
            stops.append(f"{s['color']} {inicio}% {min(acumulado, 100)}%")
        resultado.append({**s, "pct": pct})
    gradient = ", ".join(stops) if stops else "var(--border) 0% 100%"
    return {"segmentos": resultado, "gradient": gradient, "total": total}


@bp.route("/")
def index():
    stock_counts = {
        row["estado"]: row["c"]
        for row in query("SELECT estado, COUNT(*) c FROM vehiculos GROUP BY estado")
    }
    pedidos_activos = query(
        "SELECT COUNT(*) c FROM pedidos_clientes WHERE estado = 'buscando'", one=True
    )["c"]
    ventas_mes = query(
        """SELECT COUNT(*) c, COALESCE(SUM(valor_vendido - valor_compra - gastos), 0) ganancia,
                  COALESCE(SUM(valor_vendido), 0) ingresos
           FROM vehiculos
           WHERE estado = 'vendido' AND strftime('%Y-%m', fecha_venta) = strftime('%Y-%m', 'now')""",
        one=True,
    )
    gastos_en_reparacion = query(
        "SELECT COALESCE(SUM(gastos), 0) c FROM vehiculos WHERE estado = 'en_reparacion'", one=True
    )["c"]
    # Mismo criterio que el resumen de Financiación (solo planes activos):
    # cobrado = ya percibido, adeudado = cuotas pendientes = "cuotas por cobrar".
    fin_totales = query(
        """SELECT COALESCE(SUM(fc.monto), 0) total, COALESCE(SUM(fc.monto_pagado), 0) cobrado
           FROM financiacion_cuotas fc JOIN financiaciones f ON f.id = fc.financiacion_id
           WHERE f.estado = 'activo'""",
        one=True,
    )
    cuotas_por_cobrar = round(fin_totales["total"] - fin_totales["cobrado"], 2)
    ultimos_vehiculos = query(
        "SELECT * FROM vehiculos ORDER BY created_at DESC LIMIT 5"
    )
    # Indicador de mensajes sin leer (bandeja unificada — vista previa con datos de ejemplo).
    mensajes_no_leidos = contar_no_leidos()

    grafico_stock = _grafico_torta([
        {"label": "Disponible", "value": stock_counts.get("disponible", 0), "color": COLOR_DISPONIBLE},
        {"label": "Por ingresar", "value": stock_counts.get("por_ingresar", 0), "color": COLOR_POR_INGRESAR},
        {"label": "En reparación", "value": stock_counts.get("en_reparacion", 0), "color": COLOR_EN_REPARACION},
    ])
    grafico_cobros = _grafico_torta([
        {"label": "Cobrado", "value": fin_totales["cobrado"], "color": COLOR_COBRADO},
        {"label": "Adeudado (por cobrar)", "value": cuotas_por_cobrar, "color": COLOR_ADEUDADO},
    ])

    return render_template(
        "dashboard.html",
        stock_counts=stock_counts,
        pedidos_activos=pedidos_activos,
        ventas_mes=ventas_mes,
        gastos_en_reparacion=gastos_en_reparacion,
        cuotas_por_cobrar=cuotas_por_cobrar,
        ultimos_vehiculos=ultimos_vehiculos,
        mensajes_no_leidos=mensajes_no_leidos,
        grafico_stock=grafico_stock,
        grafico_cobros=grafico_cobros,
    )
