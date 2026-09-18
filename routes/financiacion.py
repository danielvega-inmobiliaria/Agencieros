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
    # Monto vencido (18/09/2026, pedido de Daniel para el resumen de
    # Financiación): saldo pendiente de las cuotas que ya vencieron y
    # todavía no se terminaron de cobrar -- a propósito NO incluye el
    # recargo por atraso (ver `_monto_sugerido_con_recargo`, que sí lo
    # suma para sugerir el monto a cobrar en una cuota puntual): acá es
    # "cuánto es la deuda original que está vencida", sin mezclar la
    # penalidad, que varía según cuándo se termine cobrando cada una.
    monto_vencido = round(
        sum(
            (c["monto"] - (c["monto_pagado"] or 0))
            for c in cuotas
            if c["estado"] != "pagada" and c["fecha_vencimiento"] and c["fecha_vencimiento"] < hoy
        ),
        2,
    )
    # Recargo por atraso cobrado (18/09/2026): no es una columna aparte en
    # la base -- se infiere de lo que se cobró de más sobre el monto de la
    # cuota (lo que exceda `monto` en una cuota pagada es, por definición,
    # el interés/recargo que se le cobró al cliente por pagar tarde).
    recargo = round(sum(max(0, (c["monto_pagado"] or 0) - c["monto"]) for c in cuotas), 2)
    f["total_plan"] = total
    f["total_cobrado"] = cobrado
    f["total_adeudado"] = round(total - cobrado, 2)
    f["total_recargo_atraso"] = recargo
    f["cuotas_vencidas"] = vencidas
    f["monto_vencido"] = monto_vencido
    f["cuotas_totales"] = len(cuotas)
    f["cuotas_pagadas"] = sum(1 for c in cuotas if c["estado"] == "pagada")
    return f


def _monto_sugerido_con_recargo(cuota, tasa_punitoria, hoy):
    """Saldo pendiente de una cuota, sumando el recargo por atraso si
    corresponde: criterio de Daniel (17/09/2026) es un % fijo que se
    acumula cada 30 días de atraso (ej. 10% si pasaron entre 30 y 59 días
    desde el vencimiento, 20% si pasaron entre 60 y 89, etc. -- no
    compuesto, se suma sobre el saldo original). Sin tasa cargada o si la
    cuota todavía no venció, devuelve el saldo tal cual."""
    saldo = round(cuota["monto"] - (cuota["monto_pagado"] or 0), 2)
    if not tasa_punitoria or not cuota["fecha_vencimiento"] or cuota["fecha_vencimiento"] >= hoy:
        return saldo
    dias_atraso = (date.fromisoformat(hoy) - date.fromisoformat(cuota["fecha_vencimiento"])).days
    bloques = dias_atraso // 30
    if bloques <= 0:
        return saldo
    return round(saldo * (1 + (bloques * tasa_punitoria) / 100), 2)


@bp.route("/")
def index():
    planes = [_con_resumen(f) for f in query("SELECT * FROM financiaciones ORDER BY created_at DESC")]
    activos = [p for p in planes if p["estado"] == "activo"]
    resumen = {
        "total_a_cobrar": sum(p["total_plan"] for p in activos),
        "total_cobrado": sum(p["total_cobrado"] for p in activos),
        "total_adeudado": sum(p["total_adeudado"] for p in activos),
        "cuotas_vencidas": sum(p["cuotas_vencidas"] for p in activos),
        "monto_vencido": round(sum(p["monto_vencido"] for p in activos), 2),
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
        "fecha_venta": request.values.get("fecha_venta", str(date.today())),
        "cuota_aplicada": request.values.get("cuota_aplicada", ""),
        "tasa_interes_punitorio": request.values.get("tasa_interes_punitorio", "0"),
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
    try:
        tasa_punitoria = float(f.get("tasa_interes_punitorio") or 0)
    except ValueError:
        tasa_punitoria = 0

    # Cuota aplicada (17/09/2026): la cuota calculada por la fórmula casi
    # nunca es un número redondo (ej. $286.667) -- Daniel la redondea a mano
    # (ej. $290.000) y ese es el monto que realmente cobra todos los meses.
    # Si cargó un valor acá, reemplaza uniformemente el monto de cada cuota
    # (incluida la última -- ya no hace falta el ajuste fino por redondeo
    # que se hace sobre la cuota calculada, porque esta ya es la real).
    try:
        cuota_aplicada = float(f.get("cuota_aplicada") or 0)
    except ValueError:
        cuota_aplicada = 0
    valor_cuota_final = cuota_aplicada if cuota_aplicada > 0 else cuota
    if cuota_aplicada > 0:
        for fila in cronograma:
            fila["monto"] = cuota_aplicada

    financiacion_id = execute(
        """INSERT INTO financiaciones
           (vehiculo_id, cliente_nombre, cliente_telefono, precio_venta, anticipo,
            monto_financiado, tasa_interes_mensual, tasa_interes_punitorio, metodo_interes,
            periodicidad, plazo_meses, cantidad_cuotas, valor_cuota, fecha_inicio, observaciones)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            vehiculo_id, f.get("cliente_nombre"), f.get("cliente_telefono") or None,
            float(f.get("precio_venta")) if f.get("precio_venta") else None,
            float(f.get("anticipo") or 0), monto, tasa, tasa_punitoria, metodo, periodicidad,
            n, len(cronograma), valor_cuota_final, str(fecha_inicio), f.get("observaciones") or None,
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
            fecha_venta = _parsear_fecha(f.get("fecha_venta"), default=date.today())
            execute(
                """UPDATE vehiculos SET estado = 'vendido', valor_vendido = ?,
                   fecha_venta = ?, updated_at = datetime('now') WHERE id = ?""",
                (precio_venta, str(fecha_venta), vehiculo_id),
            )

    flash(
        f"Plan de financiación creado — {len(cronograma)} cuotas de ${valor_cuota_final:,.0f}.".replace(",", "."),
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
    hoy = str(date.today())
    cuotas = [dict(c) for c in query(
        "SELECT * FROM financiacion_cuotas WHERE financiacion_id = ? ORDER BY numero", (financiacion_id,)
    )]
    for c in cuotas:
        c["monto_sugerido"] = (
            _monto_sugerido_con_recargo(c, fin["tasa_interes_punitorio"], hoy)
            if c["estado"] != "pagada" else None
        )
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

    # Fecha de pago (17/09/2026): por default es hoy, pero se puede cargar
    # una fecha real distinta -- para asentar cobros que ya se hicieron
    # antes (ej. al cargar un plan viejo con cuotas ya cobradas).
    fecha_pago_form = request.form.get("fecha_pago")
    fecha_pago = _parsear_fecha(fecha_pago_form, default=date.today()) if fecha_pago_form else date.today()

    nuevo_pagado = round((cuota["monto_pagado"] or 0) + monto_pagado, 2)
    nuevo_estado = "pagada" if nuevo_pagado >= cuota["monto"] - 0.01 else "pendiente"
    # 18/09/2026: la fecha de pago se guarda siempre que se registra un
    # cobro (antes solo se guardaba si el pago completaba la cuota -- un
    # pago parcial quedaba con la fecha en blanco, aunque Daniel la hubiera
    # cargado).
    execute(
        """UPDATE financiacion_cuotas SET monto_pagado = ?, estado = ?,
           fecha_pago = ? WHERE id = ?""",
        (nuevo_pagado, nuevo_estado, str(fecha_pago), cuota_id),
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


@bp.route("/<int:financiacion_id>/corregir-fechas", methods=["POST"])
def corregir_fechas(financiacion_id):
    """Recalcula el vencimiento de TODAS las cuotas a partir de una nueva
    fecha de la primera cuota (18/09/2026, pedido de Daniel después de
    cargar un plan dejando la fecha sugerida por default en vez de la real).
    No toca número, monto, pagos ni estado de ninguna cuota -- solo corre
    de nuevo el cronograma de fechas con la misma periodicidad del plan."""
    fin = query("SELECT * FROM financiaciones WHERE id = ?", (financiacion_id,), one=True)
    if not fin:
        flash("Plan de financiación no encontrado.", "error")
        return redirect(url_for("financiacion.index"))

    nueva_fecha = _parsear_fecha(request.form.get("fecha_inicio"), default=None)
    if not nueva_fecha:
        flash("Cargá una fecha válida para la primera cuota.", "error")
        return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))

    cuotas = query(
        "SELECT * FROM financiacion_cuotas WHERE financiacion_id = ? ORDER BY numero", (financiacion_id,)
    )
    for c in cuotas:
        if fin["periodicidad"] == "semanal":
            nueva_venc = nueva_fecha + timedelta(days=7 * (c["numero"] - 1))
        else:
            nueva_venc = _sumar_meses(nueva_fecha, c["numero"] - 1)
        execute(
            "UPDATE financiacion_cuotas SET fecha_vencimiento = ? WHERE id = ?",
            (str(nueva_venc), c["id"]),
        )
    execute("UPDATE financiaciones SET fecha_inicio = ? WHERE id = ?", (str(nueva_fecha), financiacion_id))
    flash("Fechas de vencimiento corregidas.", "success")
    return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))


@bp.route("/<int:financiacion_id>/tasa-punitoria", methods=["POST"])
def actualizar_tasa_punitoria(financiacion_id):
    """Carga o corrige la tasa de interés por atraso de un plan ya creado
    (18/09/2026) -- por ejemplo, para planes cargados antes de que existiera
    este campo, como el de Laura Lezcano/Chevrolet CRUZE."""
    fin = query("SELECT * FROM financiaciones WHERE id = ?", (financiacion_id,), one=True)
    if not fin:
        flash("Plan de financiación no encontrado.", "error")
        return redirect(url_for("financiacion.index"))
    try:
        tasa = float(request.form.get("tasa_interes_punitorio") or 0)
    except ValueError:
        tasa = 0
    execute("UPDATE financiaciones SET tasa_interes_punitorio = ? WHERE id = ?", (tasa, financiacion_id))
    flash("Tasa de interés por atraso actualizada.", "success")
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
