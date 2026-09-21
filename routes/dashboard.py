from datetime import date

from flask import Blueprint, render_template, session, redirect, url_for, flash, abort

from database import query, execute

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


def _senas_por_resolver(agencia_id):
    """Señas de operaciones canceladas que todavía no se decidieron
    (retener o devolver): las de Stock/venta directa (`ventas` en estado
    'cancelada') y las de reservas canceladas de Financiación. Una seña es
    siempre en efectivo (Daniel 19/09/2026)."""
    ventas = query(
        """SELECT vt.id AS id, 'venta' AS origen, vt.cliente_nombre AS cliente, vt.cliente_telefono AS telefono,
                  COALESCE(vt.sena, 0) AS monto, vt.fecha_sena AS fecha,
                  v.marca, v.modelo, v.version, v.anio, v.dominio
           FROM ventas vt JOIN vehiculos v ON v.id = vt.vehiculo_id
           WHERE vt.estado = 'cancelada' AND vt.sena_resolucion IS NULL
             AND COALESCE(vt.sena, 0) > 0
             AND vt.agencia_id = ?""",
        (agencia_id,),
    )
    planes = query(
        """SELECT f.id AS id, 'plan' AS origen, f.cliente_nombre AS cliente, f.cliente_telefono AS telefono,
                  COALESCE(f.anticipo, 0) AS monto, substr(f.created_at, 1, 10) AS fecha,
                  v.marca, v.modelo, v.version, v.anio, v.dominio
           FROM financiaciones f LEFT JOIN vehiculos v ON v.id = f.vehiculo_id
           WHERE f.estado = 'cancelado_reserva' AND f.sena_resolucion IS NULL
             AND COALESCE(f.anticipo, 0) > 0
             AND COALESCE(f.agencia_id, 1) = ?""",  # Financiación aún no guarda agencia_id al crear un plan: NULL = agencia 1
        (agencia_id,),
    )
    filas = [dict(r) for r in ventas] + [dict(r) for r in planes]
    filas.sort(key=lambda r: r["fecha"] or "", reverse=True)
    return filas


@bp.route("/senas")
def senas():
    pendientes = _senas_por_resolver(session["agencia_id"])
    return render_template(
        "dashboard_senas.html", senas=pendientes, total=sum(r["monto"] for r in pendientes)
    )


@bp.route("/senas/<origen>/<int:item_id>/<accion>", methods=["POST"])
def resolver_sena(origen, item_id, accion):
    """Decide qué hacer con una seña de una operación cancelada.
    'retener' -> la agencia se la queda: suma a "Ingresos del mes" del mes
    en que se retiene. 'devolver' -> no cambia ningún número."""
    if origen not in ("venta", "plan") or accion not in ("retener", "devolver"):
        abort(404)
    tabla, estado, campo = (
        ("ventas", "cancelada", "sena") if origen == "venta" else ("financiaciones", "cancelado_reserva", "anticipo")
    )
    fila = query(
        # Financiación aún no guarda agencia_id al crear un plan: NULL = agencia 1
        f"SELECT * FROM {tabla} WHERE id = ? AND COALESCE(agencia_id, 1) = ? AND estado = ? AND sena_resolucion IS NULL",
        (item_id, session["agencia_id"], estado), one=True,
    )
    if not fila:
        flash("Esa seña ya no está pendiente de resolver.", "error")
        return redirect(url_for("dashboard.senas"))
    resolucion = "retenida" if accion == "retener" else "devuelta"
    execute(
        f"UPDATE {tabla} SET sena_resolucion = ?, sena_resolucion_fecha = ? WHERE id = ?",
        (resolucion, str(date.today()), item_id),
    )
    monto = fila[campo] or 0
    monto_txt = "$" + "{:,.0f}".format(monto).replace(",", ".")
    if accion == "retener":
        flash(
            f"Seña de {monto_txt} retenida: suma a los Ingresos y a la Ganancia de este mes." if monto
            else "Listo: quedó resuelta (no había efectivo que retener).",
            "success",
        )
    else:
        flash("Seña marcada como devuelta." if monto else "Listo: quedó resuelta.", "success")
    return redirect(url_for("dashboard.senas"))


def efectivo_de_venta(r):
    """Efectivo que realmente entró por una venta (corregido 19/09/2026).

    Regla de oro: la SEÑA no se suma a la entrega en contado -- la entrega
    en contado es el efectivo total de la operación (precio de venta -
    permuta - monto financiado) y la seña es solo la parte de ese efectivo
    que llegó antes. Sumarlas cuenta la seña dos veces (caso Hilux: seña
    $1.000.000 + contado total $13.600.000 figuraba como $14.600.000).
      - Venta financiada: la entrega en contado (seña incluida). Si el plan
        no tiene entrega cargada (camino viejo `/financiacion/nuevo`, solo
        guardaba el anticipo), el efectivo es el anticipo. Nunca menos que
        la seña.
      - Venta directa sin financiación (tabla `ventas`): efectivo_cobrado +
        el crédito externo (banco/financiera) si lo hubo: lo desembolsa el
        prestamista al cierre, así que entra igual que el efectivo.
      - Vendido a mano desde Editar, sin plan ni venta registrada: el
        valor vendido completo (comportamiento de siempre).
    La Permuta nunca cuenta (es un vehículo) y el saldo financiado tampoco
    (entra cuota a cuota, se sigue en Financiación)."""
    if r["fin_id"] is not None:
        sena = r["anticipo"] or 0
        entrega = r["entrega_contado"] if r["entrega_contado"] is not None else sena
        return max(entrega, sena)
    if r["venta_id"] is not None:
        return (r["efectivo_cobrado"] or 0) + (r["credito_monto"] or 0)
    return r["valor_vendido"] or 0


@bp.route("/")
def index():
    # Multi-tenant (21/09/2026): TODO lo que se calcula acá sale solo de la
    # agencia logueada. Vehículos y pedidos filtran por su `agencia_id`; las
    # ventas, señas y cuotas llegan siempre a través de un vehículo propio o
    # con su propio filtro (los planes de Financiación todavía pueden tener
    # agencia_id NULL = agencia 1, de ahí el COALESCE).
    agencia_id = session["agencia_id"]
    stock_counts = {
        row["estado"]: row["c"]
        for row in query(
            "SELECT estado, COUNT(*) c FROM vehiculos WHERE agencia_id = ? GROUP BY estado",
            (agencia_id,),
        )
    }
    pedidos_activos = query(
        "SELECT COUNT(*) c FROM pedidos_clientes WHERE estado = 'buscando' AND agencia_id = ?",
        (agencia_id,), one=True,
    )["c"]
    # "Ingresos del mes" = efectivo que realmente entró por las ventas de
    # este mes (ver efectivo_de_venta). Cada vehículo cuenta UNA sola vez:
    # antes el LEFT JOIN a financiaciones traía todos los planes del auto,
    # así que uno con una reserva cancelada o un plan "Pendiente de firma"
    # de prueba aparecía duplicado y se duplicaban ingresos, ganancia y
    # cantidad de ventas. Ahora se toma el último plan que realmente
    # cerró la operación (no 'pendiente_firma' ni 'cancelado_reserva') y,
    # si no hay, la última venta directa cerrada de Stock.
    # "Ganancia" no cambia: sigue siendo la rentabilidad total de la venta
    # (precio completo - costo), se cobre ya, en cuotas o en permuta.
    ventas_mes_detalle = query(
        """SELECT v.id, v.valor_vendido, v.valor_compra, v.gastos,
                  f.id AS fin_id, f.anticipo, f.entrega_contado,
                  vt.id AS venta_id, vt.efectivo_cobrado, vt.credito_monto
           FROM vehiculos v
           LEFT JOIN financiaciones f ON f.id = (
               SELECT MAX(f2.id) FROM financiaciones f2
               WHERE f2.vehiculo_id = v.id
                 AND f2.estado NOT IN ('pendiente_firma', 'cancelado_reserva'))
           LEFT JOIN ventas vt ON vt.id = (
               SELECT MAX(v2.id) FROM ventas v2
               WHERE v2.vehiculo_id = v.id AND v2.estado = 'cerrada')
           WHERE v.estado = 'vendido' AND v.agencia_id = ?
             AND strftime('%Y-%m', v.fecha_venta) = strftime('%Y-%m', 'now')""",
        (agencia_id,),
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
        "ingresos": round(sum(efectivo_de_venta(r) for r in ventas_mes_detalle), 2),
        # Parte de esos ingresos que llegó como crédito externo (solo ventas directas).
        "creditos_externos": round(
            sum((r["credito_monto"] or 0) for r in ventas_mes_detalle if r["fin_id"] is None and r["venta_id"] is not None), 2
        ),
    }
    # Señas retenidas este mes (19/09/2026): cuando se cae una operación y
    # la agencia se queda con la seña, ese efectivo es un ingreso del mes en
    # que se decide retenerla. Las devueltas no cambian nada.
    ventas_mes["senas_retenidas"] = round(
        query(
            """SELECT COALESCE(SUM(m), 0) t FROM (
                   SELECT sena AS m FROM ventas
                   WHERE sena_resolucion = 'retenida' AND agencia_id = ?
                     AND strftime('%Y-%m', sena_resolucion_fecha) = strftime('%Y-%m', 'now')
                   UNION ALL
                   SELECT anticipo AS m FROM financiaciones
                   WHERE sena_resolucion = 'retenida' AND COALESCE(agencia_id, 1) = ?
                     AND strftime('%Y-%m', sena_resolucion_fecha) = strftime('%Y-%m', 'now'))""",
            (agencia_id, agencia_id), one=True,
        )["t"] or 0,
        2,
    )
    ventas_mes["ingresos"] = round(ventas_mes["ingresos"] + ventas_mes["senas_retenidas"], 2)
    # Una seña retenida también es ganancia (Daniel 19/09/2026): es plata
    # que se queda la agencia sin costo asociado, entra completa.
    ventas_mes["ganancia"] = round(ventas_mes["ganancia"] + ventas_mes["senas_retenidas"], 2)
    senas_pendientes = _senas_por_resolver(agencia_id)
    from routes.stock import _permutas_pendientes
    permutas_pendientes = _permutas_pendientes(agencia_id)
    gastos_en_reparacion = query(
        "SELECT COALESCE(SUM(gastos), 0) c FROM vehiculos WHERE estado = 'en_reparacion' AND agencia_id = ?",
        (agencia_id,), one=True,
    )["c"]
    # Mismo universo que el resumen de Financiación (solo planes activos),
    # pero acá se separa lo pendiente en 2: "Por cobrar" (cuota que todavía
    # no venció) y "Adeudado" (cuota vencida y no pagada) — antes se
    # mezclaban las dos bajo un solo "Adeudado (por cobrar)".
    cuotas_activas = query(
        """SELECT fc.monto, fc.monto_pagado, fc.fecha_vencimiento, fc.estado
           FROM financiacion_cuotas fc JOIN financiaciones f ON f.id = fc.financiacion_id
           WHERE f.estado = 'activo' AND COALESCE(f.agencia_id, 1) = ?""",
        (agencia_id,),
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
        senas_pendientes=senas_pendientes,
        permutas_pendientes=permutas_pendientes,
        senas_pendientes_total=sum(r["monto"] for r in senas_pendientes),
        gastos_en_reparacion=gastos_en_reparacion,
        cuotas_por_cobrar=cuotas_por_cobrar,
        grafico_stock=grafico_stock,
        grafico_cobros=grafico_cobros,
    )
