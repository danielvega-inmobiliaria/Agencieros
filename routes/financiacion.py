import calendar
from datetime import date, datetime

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


def _calcular_cuota_frances(monto, tasa_mensual_pct, n):
    """Cuota fija por sistema francés. `tasa_mensual_pct` es la tasa de interés
    mensual en % (ej. 5.5 = 5.5%/mes). Con tasa 0 devuelve cuotas simples
    (monto / n) sin interés."""
    i = (tasa_mensual_pct or 0) / 100
    if not n:
        return 0
    if i == 0:
        return round(monto / n, 2)
    factor = (i * (1 + i) ** n) / ((1 + i) ** n - 1)
    return round(monto * factor, 2)


def _generar_cronograma(monto, tasa_mensual_pct, n, fecha_inicio):
    """Devuelve (valor_cuota, [filas]) con el detalle mes a mes: interés,
    amortización de capital y saldo restante (sistema francés — cuota fija,
    la proporción interés/amortización va cambiando). La última cuota
    absorbe el centavo de diferencia por redondeo para que el saldo cierre
    exactamente en $0."""
    cuota = _calcular_cuota_frances(monto, tasa_mensual_pct, n)
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
    )


@bp.route("/simulador", methods=["GET", "POST"])
def simulador():
    vehiculos_vendidos = query(
        """SELECT * FROM vehiculos WHERE estado = 'vendido'
           AND id NOT IN (SELECT vehiculo_id FROM financiaciones WHERE vehiculo_id IS NOT NULL)
           ORDER BY fecha_venta DESC"""
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
    if request.method == "POST":
        try:
            monto = float(valores["monto_financiado"] or 0)
            tasa = float(valores["tasa_interes_mensual"] or 0)
            n = int(valores["cantidad_cuotas"] or 0)
            fecha_inicio = _parsear_fecha(valores["fecha_inicio"])
            if monto <= 0 or n <= 0:
                flash("Cargá un monto a financiar y una cantidad de cuotas válidos.", "error")
            else:
                cuota, cronograma = _generar_cronograma(monto, tasa, n, fecha_inicio)
        except ValueError:
            flash("Revisá los valores cargados (monto, tasa y cuotas deben ser números).", "error")

    return render_template(
        "financiacion/simulador.html",
        valores=valores,
        vehiculos_vendidos=vehiculos_vendidos,
        cuota=cuota,
        cronograma=cronograma,
        total_pagar=(cuota * len(cronograma)) if cuota and cronograma else None,
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

    cuota, cronograma = _generar_cronograma(monto, tasa, n, fecha_inicio)
    vehiculo_id = f.get("vehiculo_id") or None

    financiacion_id = execute(
        """INSERT INTO financiaciones
           (vehiculo_id, cliente_nombre, cliente_telefono, precio_venta, anticipo,
            monto_financiado, tasa_interes_mensual, cantidad_cuotas, valor_cuota,
            fecha_inicio, observaciones)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            vehiculo_id, f.get("cliente_nombre"), f.get("cliente_telefono") or None,
            float(f.get("precio_venta")) if f.get("precio_venta") else None,
            float(f.get("anticipo") or 0), monto, tasa, n, cuota,
            str(fecha_inicio), f.get("observaciones") or None,
        ),
    )
    for fila in cronograma:
        execute(
            """INSERT INTO financiacion_cuotas (financiacion_id, numero, fecha_vencimiento, monto)
               VALUES (?,?,?,?)""",
            (financiacion_id, fila["numero"], str(fila["fecha"]), fila["monto"]),
        )

    flash(f"Plan de financiación creado — {n} cuotas de ${cuota:,.0f}.".replace(",", "."), "success")
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
    execute("UPDATE financiaciones SET estado = 'cancelado' WHERE id = ?", (financiacion_id,))
    flash("Plan de financiación cancelado.", "success")
    return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))
