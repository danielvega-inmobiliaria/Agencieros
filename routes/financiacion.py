import calendar
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import query, execute

bp = Blueprint("financiacion", __name__, url_prefix="/financiacion")

ESTADO_PLAN_LABEL = {
    "activo": "Activo",
    "finalizado": "Finalizado",
    "cancelado": "Cancelado",
}
# Reutiliza los colores de badge ya definidos en style.css para no agregar CSS nuevo.
ESTADO_PLAN_BADGE = {"activo": "disponible", "finalizado": "vendido", "cancelado": "cancelado"}

METODO_LABEL = {"frances": "Francés (interés compuesto)", "simple": "Interés simple/directo"}
PERIODICIDAD_LABEL = {"mensual": "Mensual", "semanal": "Semanal"}


def _sumar_meses(fecha, meses):
    """Suma `meses` a una fecha respetando fin de mes (ej. 31/01 + 1 mes = 28/02)."""
    mes_total = fecha.month - 1 + meses
    anio = fecha.year + mes_total // 12
    mes = mes_total % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def _parsear_fecha(s, default=None):
    if not s:
        return default or date.today()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return default or date.today()


def _cuota_frances(monto, tasa_mensual_pct, n):
    """Cuota fija por sistema francés (interés compuesto sobre saldo). Con
    tasa 0 devuelve cuotas simples (monto / n)."""
    i = (tasa_mensual_pct or 0) / 100
    if not n:
        return 0
    if i == 0:
        return round(monto / n, 2)
    factor = (i * (1 + i) ** n) / ((1 + i) ** n - 1)
    return round(monto * factor, 2)


def _cuota_simple(monto, tasa_mensual_pct, n):
    """Interés simple/directo sobre el monto original (el método que Daniel
    ya usa en su Excel): cuota = (monto / n) x (1 + tasa%/100 x n). El
    interés total crece en línea recta según la cantidad de cuotas, no se
    recalcula sobre saldo como en el sistema francés."""
    if not n:
        return 0
    i = (tasa_mensual_pct or 0) / 100
    return round((monto / n) * (1 + i * n), 2)


def _cronograma_mensual(monto, tasa_mensual_pct, n, fecha_inicio, metodo):
    """Cronograma mes a mes. En 'frances' desglosa interés/amortización/saldo
    (interés compuesto sobre saldo decreciente). En 'simple' la cuota es
    fija por interés directo y el desglose de interés/amortización es a
    partes iguales (informativo) — Daniel no lo usa así en la práctica, pero
    sirve para mostrar de dónde sale el total. La última cuota absorbe el
    centavo de diferencia por redondeo."""
    if metodo == "simple":
        cuota = _cuota_simple(monto, tasa_mensual_pct, n)
        interes_total = round(cuota * n - monto, 2)
        amortizacion_fija = round(monto / n, 2)
        interes_fijo = round(interes_total / n, 2) if n else 0
        saldo = monto
        filas = []
        for numero in range(1, n + 1):
            saldo = round(saldo - amortizacion_fija, 2)
            filas.append({
                "numero": numero,
                "fecha": _sumar_meses(fecha_inicio, numero - 1),
                "monto": cuota,
                "interes": interes_fijo,
                "amortizacion": amortizacion_fija,
                "saldo": saldo,
            })
    else:
        cuota = _cuota_frances(monto, tasa_mensual_pct, n)
        i = (tasa_mensual_pct or 0) / 100
        saldo = monto
        filas = []
        for numero in range(1, n + 1):
            interes = round(saldo * i, 2)
            amortizacion = round(cuota - interes, 2)
            saldo = round(saldo - amortizacion, 2)
            filas.append({
                "numero": numero,
                "fecha": _sumar_meses(fecha_inicio, numero - 1),
                "monto": cuota,
                "interes": interes,
                "amortizacion": amortizacion,
                "saldo": saldo,
            })

    if filas and abs(filas[-1]["saldo"]) > 0.005:
        ajuste = filas[-1]["saldo"]
        filas[-1]["monto"] = round(filas[-1]["monto"] + ajuste, 2)
        filas[-1]["amortizacion"] = round(filas[-1]["amortizacion"] + ajuste, 2)
        filas[-1]["saldo"] = 0
    return cuota, filas


def _cronograma_semanal(cuota_mensual, plazo_meses, fecha_inicio):
    """Convierte la cuota mensual en semanal dividiendo por 4 (criterio de
    Daniel, 14/09/2026): la cantidad de cuotas semanales sale de contar
    semanas de 7 días entre la primera cuota y esa misma fecha del plazo en
    meses elegido (ej. 12 meses = mismo día del año siguiente) — por eso el
    total pagado en semanal siempre da un poco más que en mensual, no es un
    error, es el mismo criterio que ya usaba en su planilla."""
    fecha_fin = _sumar_meses(fecha_inicio, plazo_meses)
    total_dias = (fecha_fin - fecha_inicio).days
    cantidad_semanas = total_dias // 7 + 1
    cuota_semanal = round(cuota_mensual / 4, 2)
    filas = []
    for numero in range(1, cantidad_semanas + 1):
        filas.append({
            "numero": numero,
            "fecha": fecha_inicio + timedelta(days=7 * (numero - 1)),
            "monto": cuota_semanal,
            "interes": None,
            "amortizacion": None,
            "saldo": None,
        })
    return cuota_semanal, filas


def _generar_cronograma(monto, tasa_mensual_pct, plazo_meses, fecha_inicio, metodo="frances", periodicidad="mensual"):
    """`plazo_meses` es siempre el plazo del crédito en meses (lo que el
    formulario llama "Cantidad de cuotas mensuales"), tanto si el cliente
    termina pagando mes a mes como semana a semana durante ese mismo plazo.
    Devuelve (valor_primera_cuota, [filas]). Cada fila trae `interes` /
    `amortizacion` / `saldo` en None cuando no aplica (periodicidad semanal)."""
    cuota_mensual, filas_mensuales = _cronograma_mensual(monto, tasa_mensual_pct, plazo_meses, fecha_inicio, metodo)
    if periodicidad == "semanal":
        return _cronograma_semanal(cuota_mensual, plazo_meses, fecha_inicio)
    return cuota_mensual, filas_mensuales


def _con_resumen(fin):
    """Agrega a una fila de `financiaciones` los totales de cobro (a partir
    de sus cuotas) y cuántas están vencidas hoy."""
    f = dict(fin)
    cuotas = query(
        "SELECT * FROM financiacion_cuotas WHERE financiacion_id = ? ORDER BY numero", (f["id"],)
    )
    hoy = str(date.today())
    total = sum(c["monto"] for c in cuotas)
    cobrado = sum(c["monto_pagado"] or 0 for c in cuotas)
    vencidas = sum(
        1 for c in cuotas if c["estado"] != "pagada" and c["fecha_vencimiento"] and c["fecha_vencimiento"] < hoy
    )
    f["total_plan"] = total
    f["total_cobrado"] = cobrado
    f["total_adeudado"] = round(total - cobrado, 2)
    f["cuotas_vencidas"] = vencidas
    f["cuotas_totales"] = len(cuotas)
    f["cuotas_pagadas"] = sum(1 for c in cuotas if c["estado"] == "pagada")
    return f


@bp.route("/")
def index():
    planes = [_con_resumen(f) for f in query("SELECT * FROM financiaciones ORDER BY created_at DESC")]
    activos = [p for p in planes if p["estado"] == "activo"]
    resumen = {
        "total_a_cobrar": sum(p["total_plan"] for p in activos),
        "total_cobrado": sum(p["total_cobrado"] for p in activos),
        "total_adeudado": sum(p["total_adeudado"] for p in activos),
        "cuotas_vencidas": sum(p["cuotas_vencidas"] for p in activos),
    }
    return render_template(
        "financiacion/index.html",
        planes=planes,
        resumen=resumen,
        estado_label=ESTADO_PLAN_LABEL,
        estado_badge=ESTADO_PLAN_BADGE,
        metodo_label=METODO_LABEL,
        periodicidad_label=PERIODICIDAD_LABEL,
    )


@bp.route("/simulador", methods=["GET", "POST"])
def simulador():
    # Lista para el desplegable: autos Disponibles (lo más común — se arma el
    # plan de financiación como parte de la venta) y también los ya Vendidos
    # (por si la venta se cerró en Stock antes de armar el plan). No se
    # ofrecen los que ya tienen un plan de financiación activo/cargado.
    vehiculos_stock = query(
        """SELECT * FROM vehiculos WHERE estado IN ('disponible', 'vendido')
           AND id NOT IN (SELECT vehiculo_id FROM financiaciones WHERE vehiculo_id IS NOT NULL)
           ORDER BY (estado = 'disponible') DESC, COALESCE(fecha_venta, fecha_ingreso) DESC"""
    )
    valores = {
        "vehiculo_id": request.values.get("vehiculo_id", ""),
        "cliente_nombre": request.values.get("cliente_nombre", ""),
        "cliente_telefono": request.values.get("cliente_telefono", ""),
        "precio_venta": request.values.get("precio_venta", ""),
        "anticipo": request.values.get("anticipo", "0"),
        "monto_financiado": request.values.get("monto_financiado", ""),
        "tasa_interes_mensual": request.values.get("tasa_interes_mensual", "0"),
        "cantidad_cuotas": request.values.get("cantidad_cuotas", "12"),
        "fecha_inicio": request.values.get("fecha_inicio", str(date.today())),
        "metodo_interes": request.values.get("metodo_interes", "frances"),
        "periodicidad": request.values.get("periodicidad", "mensual"),
    }

    # Autocompletar monto a financiar a partir de precio de venta - anticipo,
    # si el usuario no tocó el campo a mano.
    if request.method == "POST" and not valores["monto_financiado"] and valores["precio_venta"]:
        try:
            valores["monto_financiado"] = str(
                round(float(valores["precio_venta"]) - float(valores["anticipo"] or 0), 2)
            )
        except ValueError:
            pass

    cuota = None
    cronograma = None
    desglose = valores["metodo_interes"] == "frances" and valores["periodicidad"] == "mensual"
    if request.method == "POST":
        try:
            monto = float(valores["monto_financiado"] or 0)
            tasa = float(valores["tasa_interes_mensual"] or 0)
            n = int(valores["cantidad_cuotas"] or 0)
            fecha_inicio = _parsear_fecha(valores["fecha_inicio"])
            if monto <= 0 or n <= 0:
                flash("Cargá un monto a financiar y una cantidad de cuotas válidos.", "error")
            else:
                cuota, cronograma = _generar_cronograma(
                    monto, tasa, n, fecha_inicio, valores["metodo_interes"], valores["periodicidad"]
                )
        except ValueError:
            flash("Revisá los valores cargados (monto, tasa y cuotas deben ser números).", "error")

    return render_template(
        "financiacion/simulador.html",
        valores=valores,
        vehiculos_stock=vehiculos_stock,
        estado_label={"disponible": "Disponible", "vendido": "Vendido"},
        cuota=cuota,
        cronograma=cronograma,
        desglose=desglose,
        total_pagar=(sum(f["monto"] for f in cronograma)) if cronograma else None,
        metodo_label=METODO_LABEL,
        periodicidad_label=PERIODICIDAD_LABEL,
    )


@bp.route("/nuevo", methods=["POST"])
def nuevo():
    f = request.form
    try:
        monto = float(f.get("monto_financiado") or 0)
        tasa = float(f.get("tasa_interes_mensual") or 0)
        n = int(f.get("cantidad_cuotas") or 0)
        fecha_inicio = _parsear_fecha(f.get("fecha_inicio"))
    except ValueError:
        flash("Revisá los valores del plan antes de guardarlo.", "error")
        return redirect(url_for("financiacion.simulador"))

    if not f.get("cliente_nombre") or monto <= 0 or n <= 0:
        flash("Faltan datos: cliente, monto a financiar y cantidad de cuotas son obligatorios.", "error")
        return redirect(url_for("financiacion.simulador"))

    metodo = f.get("metodo_interes") or "frances"
    periodicidad = f.get("periodicidad") or "mensual"
    cuota, cronograma = _generar_cronograma(monto, tasa, n, fecha_inicio, metodo, periodicidad)
    vehiculo_id = f.get("vehiculo_id") or None

    financiacion_id = execute(
        """INSERT INTO financiaciones
           (vehiculo_id, cliente_nombre, cliente_telefono, precio_venta, anticipo,
            monto_financiado, tasa_interes_mensual, metodo_interes, periodicidad,
            plazo_meses, cantidad_cuotas, valor_cuota, fecha_inicio, observaciones)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            vehiculo_id, f.get("cliente_nombre"), f.get("cliente_telefono") or None,
            float(f.get("precio_venta")) if f.get("precio_venta") else None,
            float(f.get("anticipo") or 0), monto, tasa, metodo, periodicidad,
            n, len(cronograma), cuota, str(fecha_inicio), f.get("observaciones") or None,
        ),
    )
    for fila in cronograma:
        execute(
            """INSERT INTO financiacion_cuotas (financiacion_id, numero, fecha_vencimiento, monto)
               VALUES (?,?,?,?)""",
            (financiacion_id, fila["numero"], str(fila["fecha"]), fila["monto"]),
        )

    # Si el auto elegido todavía estaba "Disponible" en Stock, el plan de
    # financiación ES la venta — pasa a "Vendido" para que no se siga
    # ofreciendo a otro comprador.
    if vehiculo_id:
        vehiculo = query("SELECT * FROM vehiculos WHERE id = ?", (vehiculo_id,), one=True)
        if vehiculo and vehiculo["estado"] != "vendido":
            precio_venta = float(f.get("precio_venta")) if f.get("precio_venta") else vehiculo["valor_publicado"]
            execute(
                """UPDATE vehiculos SET estado = 'vendido', valor_vendido = ?,
                   fecha_venta = ?, updated_at = datetime('now') WHERE id = ?""",
                (precio_venta, str(date.today()), vehiculo_id),
            )

    flash(
        f"Plan de financiación creado — {len(cronograma)} cuotas de ${cuota:,.0f}.".replace(",", "."),
        "success",
    )
    return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))


@bp.route("/<int:financiacion_id>")
def detalle(financiacion_id):
    fin = query("SELECT * FROM financiaciones WHERE id = ?", (financiacion_id,), one=True)
    if not fin:
        flash("Plan de financiación no encontrado.", "error")
        return redirect(url_for("financiacion.index"))
    vehiculo = None
    if fin["vehiculo_id"]:
        vehiculo = query("SELECT * FROM vehiculos WHERE id = ?", (fin["vehiculo_id"],), one=True)
    cuotas = query(
        "SELECT * FROM financiacion_cuotas WHERE financiacion_id = ? ORDER BY numero", (financiacion_id,)
    )
    hoy = str(date.today())
    return render_template(
        "financiacion/detalle.html",
        fin=_con_resumen(fin),
        vehiculo=vehiculo,
        cuotas=cuotas,
        hoy=hoy,
        estado_label=ESTADO_PLAN_LABEL,
        estado_badge=ESTADO_PLAN_BADGE,
        metodo_label=METODO_LABEL,
        periodicidad_label=PERIODICIDAD_LABEL,
    )


@bp.route("/<int:financiacion_id>/cuota/<int:cuota_id>/pagar", methods=["POST"])
def pagar_cuota(financiacion_id, cuota_id):
    cuota = query(
        "SELECT * FROM financiacion_cuotas WHERE id = ? AND financiacion_id = ?",
        (cuota_id, financiacion_id), one=True,
    )
    if not cuota:
        flash("Cuota no encontrada.", "error")
        return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))

    try:
        monto_pagado = float(request.form.get("monto_pagado") or cuota["monto"])
    except ValueError:
        monto_pagado = cuota["monto"]

    nuevo_pagado = round((cuota["monto_pagado"] or 0) + monto_pagado, 2)
    nuevo_estado = "pagada" if nuevo_pagado >= cuota["monto"] - 0.01 else "pendiente"
    execute(
        """UPDATE financiacion_cuotas SET monto_pagado = ?, estado = ?,
           fecha_pago = ? WHERE id = ?""",
        (nuevo_pagado, nuevo_estado, str(date.today()) if nuevo_estado == "pagada" else cuota["fecha_pago"], cuota_id),
    )

    # Si ya están todas pagadas, el plan pasa a finalizado automáticamente.
    pendientes = query(
        "SELECT COUNT(*) c FROM financiacion_cuotas WHERE financiacion_id = ? AND estado != 'pagada'",
        (financiacion_id,), one=True,
    )["c"]
    if pendientes == 0:
        execute("UPDATE financiaciones SET estado = 'finalizado' WHERE id = ?", (financiacion_id,))
        flash("Cuota registrada. ¡Plan finalizado, todas las cuotas están cobradas!", "success")
    else:
        flash("Pago registrado.", "success")
    return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))


@bp.route("/<int:financiacion_id>/cancelar", methods=["POST"])
def cancelar(financiacion_id):
    """Cancelar = liquidar el saldo pendiente todo junto (el vehículo ya se
    vendió y transfirió, esto no lo toca). Se recalcula cuánto hay que cobrar
    al momento de la cancelación, reconociendo una eventual quita de
    intereses: el monto final se reparte a prorrata entre las cuotas
    pendientes, que quedan todas marcadas como pagadas por ese monto (su
    `monto` se ajusta hacia abajo si hubo quita, para que no quede
    "adeudado" fantasma)."""
    fin = query("SELECT * FROM financiaciones WHERE id = ?", (financiacion_id,), one=True)
    if not fin:
        flash("Plan de financiación no encontrado.", "error")
        return redirect(url_for("financiacion.index"))
    if fin["estado"] != "activo":
        flash("Este plan ya no está activo.", "error")
        return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))

    pendientes = query(
        "SELECT * FROM financiacion_cuotas WHERE financiacion_id = ? AND estado != 'pagada' ORDER BY numero",
        (financiacion_id,),
    )
    saldo_original = round(sum(c["monto"] - (c["monto_pagado"] or 0) for c in pendientes), 2)

    try:
        monto_final = float(request.form.get("monto_final"))
    except (TypeError, ValueError):
        monto_final = saldo_original
    monto_final = max(round(monto_final, 2), 0)

    hoy = str(date.today())
    if pendientes and saldo_original > 0:
        acumulado = 0
        for idx, c in enumerate(pendientes):
            saldo_cuota = c["monto"] - (c["monto_pagado"] or 0)
            if idx == len(pendientes) - 1:
                # La última cuota se lleva la diferencia de redondeo.
                aporte = round(monto_final - acumulado, 2)
            else:
                aporte = round(saldo_cuota / saldo_original * monto_final, 2)
                acumulado += aporte
            aporte = max(aporte, 0)
            nuevo_pagado = round((c["monto_pagado"] or 0) + aporte, 2)
            execute(
                """UPDATE financiacion_cuotas SET monto = ?, monto_pagado = ?,
                   estado = 'pagada', fecha_pago = ? WHERE id = ?""",
                (nuevo_pagado, nuevo_pagado, hoy, c["id"]),
            )

    quita = round(saldo_original - monto_final, 2)
    nota = f"[Cancelado {hoy}] Saldo pendiente ${saldo_original:,.0f} liquidado por ${monto_final:,.0f}".replace(",", ".")
    if quita > 0.5:
        nota += f" (quita de intereses ${quita:,.0f})".replace(",", ".")
    observaciones = f"{fin['observaciones']}\n{nota}" if fin["observaciones"] else nota
    execute(
        "UPDATE financiaciones SET estado = 'cancelado', observaciones = ? WHERE id = ?",
        (observaciones, financiacion_id),
    )
    flash(f"Plan cancelado — saldo liquidado por ${monto_final:,.0f}.".replace(",", "."), "success")
    return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))
