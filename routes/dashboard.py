from datetime import date

from flask import Blueprint, render_template

from database import query

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

# Reutiliza los mismos colores que ya usan los badges en toda la app
# (Stock/Financiación), para que los gráficos del dashboard no introduzcan
# una paleta nueva — así Daniel ya sabe qué significa cada color.
COLOR_DISPONIBLE = "var(--green)"
COLOR_POR_INGRESAR = "var(--gold-light)"
COLOR_EN_REPARACION = "var(--red)"
# Cobrado = verde, Por cobrar (cuota pendiente pero todavía no vencida) =
# amarillo, Adeudado (cuota pendiente y ya vencida) = rojo — pedido explícito
# de Daniel 15/09/2026 (continuación 16), mismo criterio de colores que ya
# usa el resto de la app para "ok / atención / problema".
COLOR_COBRADO = "var(--green)"
COLOR_POR_COBRAR = "var(--gold-light)"
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
    # "Ingresos del mes" tiene que reflejar el efectivo que realmente entró
    # este mes, no el precio de venta completo: si el vehículo se vendió con
    # un plan de financiación, lo que se cobró al contado en el momento de
    # la venta es el anticipo (el resto llega después, cuota a cuota, y ya
    # se sigue por separado en "Cuotas por cobrar"/Financiación) — pedido de
    # Daniel 15/09/2026 (continuación 23). Si no hay plan de financiación
    # ligado al vehículo, la venta fue de contado por el valor completo.
    # "Ganancia" no cambia: sigue siendo la rentabilidad total de la venta
    # (precio completo - costo), se cobre ya o en cuotas.
    ventas_mes_detalle = query(
        """SELECT v.valor_vendido, v.valor_compra, v.gastos, f.anticipo, f.entrega_contado
           FROM vehiculos v
           LEFT JOIN financiaciones f ON f.vehiculo_id = v.id
           WHERE v.estado = 'vendido' AND strftime('%Y-%m', v.fecha_venta) = strftime('%Y-%m', 'now')"""
    )
    ventas_mes = {
        "c": len(ventas_mes_detalle),
        "ganancia": round(
            sum(
                (r["valor_vendido"] or 0) - (r["valor_compra"] or 0) - (r["gastos"] or 0)
                for r in ventas_mes_detalle
            ),
            2,
        ),
        # 19/09/2026 (bug reportado por Daniel): si el vehículo se vendió
        # con un plan de financiación que además tenía "Entrega en
        # contado" (además de la seña), ese efectivo también entró este
        # mes -- antes solo se contaba la seña (`anticipo`) y la entrega
        # en contado quedaba afuera. La Permuta (vehículo, no efectivo) se
        # sigue sin contar acá a propósito.
        "ingresos": round(
            sum(
                (
                    (r["anticipo"] or 0) + (r["entrega_contado"] or 0)
                    if r["anticipo"] is not None
                    else (r["valor_vendido"] or 0)
                )
                for r in ventas_mes_detalle
            ),
            2,
        ),
    }
    gastos_en_reparacion = query(
        "SELECT COALESCE(SUM(gastos), 0) c FROM vehiculos WHERE estado = 'en_reparacion'", one=True
    )["c"]
    # Mismo universo que el resumen de Financiación (solo planes activos),
    # pero acá se separa lo pendiente en 2: "Por cobrar" (cuota que todavía
    # no venció) y "Adeudado" (cuota vencida y no pagada) — antes se
    # mezclaban las dos bajo un solo "Adeudado (por cobrar)".
    cuotas_activas = query(
        """SELECT fc.monto, fc.monto_pagado, fc.fecha_vencimiento, fc.estado
           FROM financiacion_cuotas fc JOIN financiaciones f ON f.id = fc.financiacion_id
           WHERE f.estado = 'activo'"""
    )
    hoy = str(date.today())
    cobrado = sum(c["monto_pagado"] or 0 for c in cuotas_activas)
    adeudado = sum(
        c["monto"] - (c["monto_pagado"] or 0)
        for c in cuotas_activas
        if c["estado"] != "pagada" and c["fecha_vencimiento"] and c["fecha_vencimiento"] < hoy
    )
    por_cobrar_no_vencido = sum(
        c["monto"] - (c["monto_pagado"] or 0)
        for c in cuotas_activas
        if c["estado"] != "pagada" and not (c["fecha_vencimiento"] and c["fecha_vencimiento"] < hoy)
    )
    cuotas_por_cobrar = round(adeudado + por_cobrar_no_vencido, 2)
    grafico_stock = _grafico_torta([
        {"label": "Disponible", "value": stock_counts.get("disponible", 0), "color": COLOR_DISPONIBLE},
        {"label": "Por ingresar", "value": stock_counts.get("por_ingresar", 0), "color": COLOR_POR_INGRESAR},
        {"label": "En reparación", "value": stock_counts.get("en_reparacion", 0), "color": COLOR_EN_REPARACION},
    ])
    grafico_cobros = _grafico_torta([
        {"label": "Cobrado", "value": round(cobrado, 2), "color": COLOR_COBRADO},
        {"label": "Por cobrar", "value": round(por_cobrar_no_vencido, 2), "color": COLOR_POR_COBRAR},
        {"label": "Adeudado (vencido)", "value": round(adeudado, 2), "color": COLOR_ADEUDADO},
    ])

    return render_template(
        "dashboard.html",
        stock_counts=stock_counts,
        pedidos_activos=pedidos_activos,
        ventas_mes=ventas_mes,
        gastos_en_reparacion=gastos_en_reparacion,
        cuotas_por_cobrar=cuotas_por_cobrar,
        grafico_stock=grafico_stock,
        grafico_cobros=grafico_cobros,
    )
