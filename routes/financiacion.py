import calendar
import json
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import query, execute, obtener_catalogo

bp = Blueprint("financiacion", __name__, url_prefix="/financiacion")

ESTADO_PLAN_LABEL = {
    "pendiente_firma": "Pendiente de firma",
    "activo": "Activo",
    "finalizado": "Finalizado",
    "cancelado": "Cancelado",
    "cancelado_reserva": "Reserva cancelada",
}
# Reutiliza los colores de badge ya definidos en style.css para no agregar CSS nuevo.
ESTADO_PLAN_BADGE = {
    "pendiente_firma": "por_ingresar",
    "activo": "disponible",
    "finalizado": "vendido",
    "cancelado": "cancelado",
    "cancelado_reserva": "cancelado",
}

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
    # Las reservas canceladas ("Cancelar reserva") ya no se muestran acá
    # (pedido de Daniel 19/09/2026): la seña, si la hubo, queda en "Señas
    # por resolver" del Dashboard.
    planes = [
        _con_resumen(f)
        for f in query("SELECT * FROM financiaciones WHERE estado != 'cancelado_reserva' ORDER BY created_at DESC")
    ]
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


def _tasaciones_disponibles(excluir_tasacion_id=None):
    """Tasaciones que se pueden ofrecer como origen del valor de una
    Permuta (19/09/2026): cualquiera ya hecha en el módulo de Toma y
    tasación, salvo la que ya esté usada como permuta de otro crédito --
    `excluir_tasacion_id` deja pasar la que ya tenía elegida el propio
    plan que se está editando, si la tuviera."""
    filas = query(
        """SELECT * FROM tasaciones
           WHERE (
               id NOT IN (
                   SELECT permuta_tasacion_id FROM financiaciones
                   WHERE permuta_tasacion_id IS NOT NULL
               )
               AND id NOT IN (
                   SELECT permuta_tasacion_id FROM ventas
                   WHERE permuta_tasacion_id IS NOT NULL AND estado IN ('senado', 'cerrada')
               )
           ) OR id = ?
           ORDER BY created_at DESC""",
        (excluir_tasacion_id or 0,),
    )
    return filas


def _catalogo_json():
    """Catálogo (Año/Marca/Modelo/Versión) para el autocompletar, listo para
    incrustar dentro de un <script> sin que un "</script>" en un dato lo corte."""
    return json.dumps(obtener_catalogo()).replace("</", "<\\/")


def _leer_permuta_plan(f, excluir_tasacion_id=None):
    """Permuta del formulario de un plan -> (datos, error). Misma regla que
    la seña de Stock (19/09/2026): sin tildar "hay permuta" no hay permuta; con
    una tasación ya hecha, Año/Marca/Modelo/Versión salen de ella; si no está
    tasado hay que cargar como mínimo Año, Marca y Modelo (Versión y Km si se
    saben) para poder cruzarlo con los pedidos. El precio de toma es editable
    y puede quedar vacío mientras el plan está pendiente."""
    from routes.stock import _leer_permuta_sena
    return _leer_permuta_sena(f, _tasaciones_disponibles(excluir_tasacion_id=excluir_tasacion_id))


def _aviso_matches_permuta(permuta):
    """Flash con los compradores que ya buscan el vehículo de la permuta."""
    if not permuta:
        return
    from flask import session
    from routes.pedidos import _buscar_matches_permuta
    propios, red = _buscar_matches_permuta(session["agencia_id"], permuta["marca"], permuta["modelo"])
    partes = []
    if propios:
        partes.append(f"{len(propios)} pedido(s) propio(s)")
    if red:
        partes.append(f"{len(red)} publicación(es) de la Red")
    if partes:
        flash("⚡ La permuta ya tiene comprador: matchea con " + " y ".join(partes) + ".", "success")


@bp.route("/simulador")
def simulador():
    # 19/09/2026 (pedido de Daniel): el simulador dejó de tener un paso
    # intermedio de "Calcular cuotas" con ida y vuelta al servidor -- la
    # cuota calculada/aplicada/total a pagar/total de interés se calculan
    # en vivo con JS apenas se cargan monto/tasa/plazo. El botón "Avanzar"
    # abre (con JS, sin ida y vuelta al servidor) el resto de los datos --
    # cliente, vehículo a vender, permuta, entrega contado, seña y
    # garantes -- y recién el botón "Guardar" manda todo junto a
    # /financiacion/guardar. Acá solo hace falta juntar las listas para
    # los dos <select> de esa segunda parte (vehículos y tasaciones).
    vehiculos_disponibles = query(
        "SELECT * FROM vehiculos WHERE estado = 'disponible' ORDER BY created_at DESC"
    )
    tasaciones_disponibles = _tasaciones_disponibles()
    # Viene de Stock -> "Vender con financiación propia" (?vehiculo_id=N): el
    # vehículo llega preseleccionado y con su precio publicado como precio de venta.
    vehiculo_pre = None
    pedido = request.args.get("vehiculo_id", type=int)
    if pedido:
        vehiculo_pre = next((v for v in vehiculos_disponibles if v["id"] == pedido), None)
    return render_template(
        "financiacion/simulador.html",
        vehiculo_pre=vehiculo_pre,
        precio_pre=int(vehiculo_pre["valor_publicado"]) if vehiculo_pre and vehiculo_pre["valor_publicado"] else "",
        metodo_label=METODO_LABEL,
        periodicidad_label=PERIODICIDAD_LABEL,
        vehiculos_disponibles=vehiculos_disponibles,
        tasaciones_disponibles=tasaciones_disponibles,
        catalogo_json=_catalogo_json(),
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

    # Datos extra para completar un crédito "Pendiente de firma" (18/09/2026):
    # garantes ya cargados y vehículos que se pueden relacionar -- los
    # Disponibles de Stock más el que ya esté señado por ESTE mismo plan
    # (si no, al recargar la página desaparecería del <select>).
    garantes = query(
        "SELECT * FROM garantes WHERE financiacion_id = ? ORDER BY id", (financiacion_id,)
    ) if fin["estado"] == "pendiente_firma" else []
    vehiculos_disponibles = query(
        "SELECT * FROM vehiculos WHERE estado = 'disponible' OR id = ? ORDER BY created_at DESC",
        (fin["vehiculo_id"] or 0,),
    ) if fin["estado"] == "pendiente_firma" else []
    # Tasaciones para corregir la Permuta desde esta misma ficha (19/09/2026):
    # deja pasar la que ya tenía elegida este plan, si la tuviera.
    tasaciones_disponibles = (
        _tasaciones_disponibles(excluir_tasacion_id=fin["permuta_tasacion_id"])
        if fin["estado"] == "pendiente_firma" else []
    )

    return render_template(
        "financiacion/detalle.html",
        fin=_con_resumen(fin),
        vehiculo=vehiculo,
        cuotas=cuotas,
        hoy=hoy,
        garantes=garantes,
        vehiculos_disponibles=vehiculos_disponibles,
        tasaciones_disponibles=tasaciones_disponibles,
        catalogo_json=_catalogo_json(),
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


@bp.route("/guardar", methods=["POST"])
def guardar():
    """Guardar un crédito "Pendiente de firma" con todo lo juntado en la
    segunda parte del simulador (19/09/2026, rediseño del botón "Avanzar"
    pedido por Daniel): a diferencia del viejo "Otorgar" -- que guardaba
    apenas con monto/tasa/plazo y todo lo demás se completaba después en
    la ficha del plan -- acá ya llega de una vehículo, cliente, permuta,
    entrega contado, seña y la lista completa de garantes (cargados como
    filas dinámicas en el mismo formulario, sin guardarse de a uno). Nada
    de esto se guardó antes de este POST -- "Avanzar" en el simulador solo
    mostraba estos campos con JS. Sigue en 'pendiente_firma': falta que
    los garantes vengan a firmar antes de "Cerrar operación"."""
    f = request.form
    try:
        monto = float(f.get("monto_financiado") or 0)
        tasa = float(f.get("tasa_interes_mensual") or 0)
        n = int(f.get("cantidad_cuotas") or 0)
        fecha_inicio = _parsear_fecha(f.get("fecha_inicio"))
    except ValueError:
        flash("Revisá los valores antes de guardar el crédito.", "error")
        return redirect(url_for("financiacion.simulador"))

    if monto <= 0 or n <= 0:
        flash("Cargá un monto a financiar y una cantidad de cuotas válidos.", "error")
        return redirect(url_for("financiacion.simulador"))

    # Permuta (19/09/2026): se valida antes de tocar nada (el vehículo pasa a
    # Señado más abajo). Ver `_leer_permuta_plan`.
    permuta, error_permuta = _leer_permuta_plan(f)
    if error_permuta:
        flash(error_permuta, "error")
        return redirect(url_for("financiacion.simulador"))

    metodo = f.get("metodo_interes") or "frances"
    periodicidad = f.get("periodicidad") or "mensual"
    cuota, cronograma = _generar_cronograma(monto, tasa, n, fecha_inicio, metodo, periodicidad)
    try:
        tasa_punitoria = float(f.get("tasa_interes_punitorio") or 0)
    except ValueError:
        tasa_punitoria = 0
    try:
        cuota_aplicada = float(f.get("cuota_aplicada") or 0)
    except ValueError:
        cuota_aplicada = 0
    valor_cuota_final = cuota_aplicada if cuota_aplicada > 0 else cuota
    if cuota_aplicada > 0:
        for fila in cronograma:
            fila["monto"] = cuota_aplicada

    # Vehículo a vender (opcional en este paso, igual que antes): si está
    # Disponible, pasa a "Señado" para dejar de ofrecerse mientras se
    # espera la firma.
    vehiculo_id = f.get("vehiculo_id") or None
    vehiculo_id = int(vehiculo_id) if vehiculo_id else None
    if vehiculo_id:
        vehiculo = query("SELECT * FROM vehiculos WHERE id = ?", (vehiculo_id,), one=True)
        if vehiculo and vehiculo["estado"] == "disponible":
            execute(
                "UPDATE vehiculos SET estado = 'senado', updated_at = datetime('now') WHERE id = ?",
                (vehiculo_id,),
            )

    # `permuta_valor` es siempre el número final que se cargó en el campo
    # (sugerido por la tasación, editable/redondeable), tasación de por
    # medio o no; puede quedar vacío si todavía no se tasó.
    p = permuta or {}

    try:
        precio_venta = float(f.get("precio_venta")) if f.get("precio_venta") else None
    except ValueError:
        precio_venta = None
    try:
        entrega_contado = float(f.get("entrega_contado")) if f.get("entrega_contado") else None
    except ValueError:
        entrega_contado = None
    try:
        anticipo = float(f.get("anticipo") or 0)
    except ValueError:
        anticipo = 0

    # cliente_nombre es NOT NULL en la base -- si todavía no se cargó, se
    # guarda vacío ("") en vez de NULL, y se completa después en la ficha
    # del plan (completar_datos).
    financiacion_id = execute(
        """INSERT INTO financiaciones
           (cliente_nombre, cliente_telefono, vehiculo_id, precio_venta, anticipo,
            permuta_tasacion_id, permuta_valor, permuta_descripcion, entrega_contado,
            permuta_marca, permuta_modelo, permuta_version, permuta_anio, permuta_km,
            monto_financiado, tasa_interes_mensual, tasa_interes_punitorio, metodo_interes,
            periodicidad, plazo_meses, cantidad_cuotas, valor_cuota, fecha_inicio, estado)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'pendiente_firma')""",
        (
            f.get("cliente_nombre") or "", f.get("cliente_telefono") or None,
            vehiculo_id, precio_venta, anticipo,
            p.get("tasacion_id"), p.get("valor"), p.get("desc"), entrega_contado,
            p.get("marca"), p.get("modelo"), p.get("version"), p.get("anio"), p.get("km"),
            monto, tasa, tasa_punitoria, metodo, periodicidad,
            n, len(cronograma), valor_cuota_final, str(fecha_inicio),
        ),
    )
    for fila in cronograma:
        execute(
            """INSERT INTO financiacion_cuotas (financiacion_id, numero, fecha_vencimiento, monto)
               VALUES (?,?,?,?)""",
            (financiacion_id, fila["numero"], str(fila["fecha"]), fila["monto"]),
        )

    # Garantes (19/09/2026): filas dinámicas del mismo formulario, ninguna
    # se guardó antes de este POST -- llegan como listas paralelas
    # (garante_nombre[], garante_dni[], etc.), una fila por posición. Se
    # ignoran las filas sin nombre (por ejemplo una fila que se agregó y
    # se dejó vacía sin usar el botón de quitar).
    nombres = f.getlist("garante_nombre[]")
    dnis = f.getlist("garante_dni[]")
    telefonos = f.getlist("garante_telefono[]")
    domicilios = f.getlist("garante_domicilio[]")
    for i, nombre in enumerate(nombres):
        nombre = (nombre or "").strip()
        if not nombre:
            continue
        execute(
            """INSERT INTO garantes (financiacion_id, nombre, dni, telefono, domicilio)
               VALUES (?,?,?,?,?)""",
            (
                financiacion_id, nombre,
                (dnis[i] or None) if i < len(dnis) else None,
                (telefonos[i] or None) if i < len(telefonos) else None,
                (domicilios[i] or None) if i < len(domicilios) else None,
            ),
        )

    flash(
        f"Crédito guardado, pendiente de firma — {len(cronograma)} cuotas de ${valor_cuota_final:,.0f}.".replace(",", "."),
        "success",
    )
    _aviso_matches_permuta(permuta)
    return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))


@bp.route("/<int:financiacion_id>/completar-datos", methods=["POST"])
def completar_datos(financiacion_id):
    """Carga o corrige cliente/vehículo/precio/seña de un crédito todavía
    'pendiente_firma' -- se puede llamar varias veces mientras se van
    juntando los datos (18/09/2026). Si se elige un vehículo Disponible,
    pasa a 'Señado' para dejar de ofrecerlo; si se cambia por otro, el
    anterior (si estaba señado por este mismo plan) vuelve a Disponible."""
    fin = query("SELECT * FROM financiaciones WHERE id = ?", (financiacion_id,), one=True)
    if not fin:
        flash("Plan de financiación no encontrado.", "error")
        return redirect(url_for("financiacion.index"))
    if fin["estado"] != "pendiente_firma":
        flash("Este plan ya no está pendiente de firma.", "error")
        return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))

    f = request.form
    # Permuta (19/09/2026): se valida antes de tocar el estado de los vehículos.
    permuta, error_permuta = _leer_permuta_plan(f, excluir_tasacion_id=fin["permuta_tasacion_id"])
    if error_permuta:
        flash(error_permuta, "error")
        return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))
    p = permuta or {}
    nuevo_vehiculo_id = f.get("vehiculo_id") or None
    nuevo_vehiculo_id = int(nuevo_vehiculo_id) if nuevo_vehiculo_id else None

    if fin["vehiculo_id"] and fin["vehiculo_id"] != nuevo_vehiculo_id:
        anterior = query("SELECT * FROM vehiculos WHERE id = ?", (fin["vehiculo_id"],), one=True)
        if anterior and anterior["estado"] == "senado":
            execute(
                "UPDATE vehiculos SET estado = 'disponible', updated_at = datetime('now') WHERE id = ?",
                (fin["vehiculo_id"],),
            )

    if nuevo_vehiculo_id:
        vehiculo = query("SELECT * FROM vehiculos WHERE id = ?", (nuevo_vehiculo_id,), one=True)
        if vehiculo and vehiculo["estado"] == "disponible":
            execute(
                "UPDATE vehiculos SET estado = 'senado', updated_at = datetime('now') WHERE id = ?",
                (nuevo_vehiculo_id,),
            )

    try:
        precio_venta = float(f.get("precio_venta")) if f.get("precio_venta") else None
    except ValueError:
        precio_venta = None
    try:
        anticipo = float(f.get("anticipo")) if f.get("anticipo") else 0
    except ValueError:
        anticipo = 0

    # Permuta + Entrega Contado (19/09/2026): se pueden corregir acá igual
    # que en el simulador -- valor siempre editable/redondeable, con o sin
    # tasación elegida (la permuta ya se leyó arriba).
    try:
        entrega_contado = float(f.get("entrega_contado")) if f.get("entrega_contado") else None
    except ValueError:
        entrega_contado = None

    execute(
        """UPDATE financiaciones SET cliente_nombre = ?, cliente_telefono = ?,
           vehiculo_id = ?, precio_venta = ?, anticipo = ?,
           permuta_tasacion_id = ?, permuta_valor = ?, permuta_descripcion = ?,
           permuta_marca = ?, permuta_modelo = ?, permuta_version = ?, permuta_anio = ?, permuta_km = ?,
           entrega_contado = ? WHERE id = ?""",
        (
            f.get("cliente_nombre") or "", f.get("cliente_telefono") or None,
            nuevo_vehiculo_id, precio_venta, anticipo,
            p.get("tasacion_id"), p.get("valor"), p.get("desc"),
            p.get("marca"), p.get("modelo"), p.get("version"), p.get("anio"), p.get("km"),
            entrega_contado,
            financiacion_id,
        ),
    )
    flash("Datos guardados.", "success")
    _aviso_matches_permuta(permuta)
    return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))


@bp.route("/<int:financiacion_id>/garantes/agregar", methods=["POST"])
def agregar_garante(financiacion_id):
    fin = query("SELECT * FROM financiaciones WHERE id = ?", (financiacion_id,), one=True)
    if not fin:
        flash("Plan de financiación no encontrado.", "error")
        return redirect(url_for("financiacion.index"))
    nombre = (request.form.get("nombre") or "").strip()
    if not nombre:
        flash("El nombre del garante es obligatorio.", "error")
        return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))
    execute(
        """INSERT INTO garantes (financiacion_id, nombre, dni, telefono, domicilio)
           VALUES (?,?,?,?,?)""",
        (
            financiacion_id, nombre,
            request.form.get("dni") or None,
            request.form.get("telefono") or None,
            request.form.get("domicilio") or None,
        ),
    )
    flash("Garante agregado.", "success")
    return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))


@bp.route("/<int:financiacion_id>/garantes/<int:garante_id>/eliminar", methods=["POST"])
def eliminar_garante(financiacion_id, garante_id):
    execute("DELETE FROM garantes WHERE id = ? AND financiacion_id = ?", (garante_id, financiacion_id))
    flash("Garante eliminado.", "success")
    return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))


@bp.route("/<int:financiacion_id>/eliminar", methods=["POST"])
def eliminar(financiacion_id):
    """Borra por completo un plan 'pendiente_firma' -- pensado para los
    casos en los que se guardó por error o solo probando el simulador
    (19/09/2026, pedido de Daniel: "me aparecen financiaciones que no
    existen" -- entradas vacías que había cargado sin querer al probar el
    flujo nuevo). Solo se puede borrar mientras sigue pendiente de firma
    -- no se toca nunca un plan Activo/Finalizado/Cancelado, ahí ya hay
    historia real de cobros de por medio y "Cancelar reserva" es el
    camino correcto en su lugar. Si el vehículo estaba 'Señado' por este
    plan, vuelve a 'Disponible'."""
    fin = query("SELECT * FROM financiaciones WHERE id = ?", (financiacion_id,), one=True)
    if not fin:
        flash("Plan de financiación no encontrado.", "error")
        return redirect(url_for("financiacion.index"))
    if fin["estado"] != "pendiente_firma":
        flash("Solo se puede eliminar un plan que todavía está pendiente de firma.", "error")
        return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))

    if fin["vehiculo_id"]:
        vehiculo = query("SELECT * FROM vehiculos WHERE id = ?", (fin["vehiculo_id"],), one=True)
        if vehiculo and vehiculo["estado"] == "senado":
            execute(
                "UPDATE vehiculos SET estado = 'disponible', updated_at = datetime('now') WHERE id = ?",
                (fin["vehiculo_id"],),
            )

    execute("DELETE FROM garantes WHERE financiacion_id = ?", (financiacion_id,))
    execute("DELETE FROM financiacion_cuotas WHERE financiacion_id = ?", (financiacion_id,))
    execute("DELETE FROM financiaciones WHERE id = ?", (financiacion_id,))
    flash("Plan eliminado -- no queda ningún registro de esto.", "success")
    return redirect(url_for("financiacion.index"))


@bp.route("/<int:financiacion_id>/confirmar-venta", methods=["POST"])
def confirmar_venta(financiacion_id):
    """Cierra el trámite: el vehículo pasa de 'Señado' (o 'Disponible', si
    no se había marcado por algún motivo) a 'Vendido', y el plan pasa de
    'pendiente_firma' a 'activo' -- recién ahí empieza a poder cobrarse
    cuota a cuota, igual que un plan cargado por el camino de siempre."""
    fin = query("SELECT * FROM financiaciones WHERE id = ?", (financiacion_id,), one=True)
    if not fin:
        flash("Plan de financiación no encontrado.", "error")
        return redirect(url_for("financiacion.index"))
    if fin["estado"] != "pendiente_firma":
        flash("Este plan ya no está pendiente de firma.", "error")
        return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))
    if not fin["cliente_nombre"] or not fin["vehiculo_id"]:
        flash("Cargá cliente y vehículo antes de confirmar la venta.", "error")
        return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))

    vehiculo = query("SELECT * FROM vehiculos WHERE id = ?", (fin["vehiculo_id"],), one=True)
    if vehiculo:
        precio_venta = fin["precio_venta"] or vehiculo["valor_publicado"]
        execute(
            """UPDATE vehiculos SET estado = 'vendido', valor_vendido = ?,
               fecha_venta = ?, updated_at = datetime('now') WHERE id = ?""",
            (precio_venta, str(date.today()), fin["vehiculo_id"]),
        )
    execute("UPDATE financiaciones SET estado = 'activo' WHERE id = ?", (financiacion_id,))
    flash("Operación cerrada — el plan pasa a activo y el vehículo a Vendido.", "success")
    if fin["permuta_marca"]:
        # El vehículo de la permuta sigue disponible para matchear ("Posible entrega")
        # hasta que se decida qué hacer con él (ingresa a Stock o va a reparación).
        return redirect(url_for("stock.permuta_destino", origen="plan", item_id=financiacion_id))
    return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))


@bp.route("/<int:financiacion_id>/cancelar-reserva", methods=["POST"])
def cancelar_reserva(financiacion_id):
    """Si se cae la firma con los garantes: el vehículo (si estaba
    'Señado' por este plan) vuelve a 'Disponible' para poder ofrecerse de
    nuevo, y el plan queda 'cancelado_reserva' -- distinto del 'cancelado'
    que usa /cancelar (esa es una liquidación anticipada de un plan que ya
    estaba activo cobrándose). La seña recibida, si la hubo, queda anotada
    en observaciones para que Daniel decida a mano si corresponde
    devolverla o no."""
    fin = query("SELECT * FROM financiaciones WHERE id = ?", (financiacion_id,), one=True)
    if not fin:
        flash("Plan de financiación no encontrado.", "error")
        return redirect(url_for("financiacion.index"))
    if fin["estado"] != "pendiente_firma":
        flash("Este plan ya no está pendiente de firma.", "error")
        return redirect(url_for("financiacion.detalle", financiacion_id=financiacion_id))

    if fin["vehiculo_id"]:
        vehiculo = query("SELECT * FROM vehiculos WHERE id = ?", (fin["vehiculo_id"],), one=True)
        if vehiculo and vehiculo["estado"] == "senado":
            execute(
                "UPDATE vehiculos SET estado = 'disponible', updated_at = datetime('now') WHERE id = ?",
                (fin["vehiculo_id"],),
            )

    hoy = str(date.today())
    nota = f"[Reserva cancelada {hoy}]"
    if fin["anticipo"]:
        nota += f" Seña recibida: ${fin['anticipo']:,.0f} -- a definir si se devuelve.".replace(",", ".")
    observaciones = f"{fin['observaciones']}\n{nota}" if fin["observaciones"] else nota
    execute(
        "UPDATE financiaciones SET estado = 'cancelado_reserva', observaciones = ? WHERE id = ?",
        (observaciones, financiacion_id),
    )
    if fin["anticipo"]:
        flash(
            "Reserva cancelada — el vehículo vuelve a Disponible. La seña quedó en \"Señas por resolver\" "
            "del Dashboard para que decidas si la retenés o la devolvés.",
            "success",
        )
    else:
        flash("Reserva cancelada — el vehículo vuelve a Disponible.", "success")
    return redirect(url_for("financiacion.index"))
