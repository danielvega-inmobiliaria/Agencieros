import os
import uuid
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort, session
from urllib.parse import quote_plus

from database import query, execute, foto_principal, obtener_catalogo, obtener_config_agencia
from storage import uploads_dir
from sync_stock import sync_stock
from buscador import parsear_filtros, buscar_combinado
from ocr_titulo import extraer_datos_titulo, TesseractNoDisponible
from equipamiento_destacado import equipamiento_destacado

bp = Blueprint("stock", __name__, url_prefix="/stock")

ESTADOS = ["disponible", "por_ingresar", "en_reparacion", "senado", "vendido"]
ESTADO_LABEL = {
    "disponible": "Disponible",
    "por_ingresar": "Por ingresar",
    "en_reparacion": "En reparación",
    "senado": "Señado",
    "vendido": "Vendido",
}
EXTENSIONES_PERMITIDAS = {"jpg", "jpeg", "png", "webp", "gif"}


def _rentabilidad(v):
    costo = (v["valor_compra"] or 0) + (v["gastos"] or 0)
    referencia = v["valor_vendido"] if v["estado"] == "vendido" and v["valor_vendido"] else v["valor_publicado"]
    ganancia_bruta = (referencia or 0) - costo
    rentabilidad_pct = (ganancia_bruta / costo * 100) if costo else 0
    dias = None
    if v["fecha_ingreso"]:
        fin = v["fecha_venta"] or str(date.today())
        try:
            d1 = date.fromisoformat(v["fecha_ingreso"][:10])
            d2 = date.fromisoformat(fin[:10])
            dias = (d2 - d1).days
        except ValueError:
            dias = None
    return {
        "costo_total": costo,
        "ganancia_bruta": ganancia_bruta,
        "rentabilidad_pct": rentabilidad_pct,
        "dias_en_stock": dias,
    }


@bp.route("/sincronizar", methods=["POST"])
def sincronizar():
    # "Sincronizar desde STOCK" lee de una carpeta fija en la compu de
    # Daniel (03_AUTOMOTOR/STOCK/) -- no tiene sentido para otra agencia
    # (no tiene esa carpeta), así que queda bloqueado para cualquiera que
    # no sea la agencia 1 (mismo bloqueo puntual que ya usa app.py para
    # módulos enteros, acá aplicado a una sola ruta dentro de Stock, que
    # para el resto ya es multi-tenant).
    if session.get("agencia_id") != 1:
        abort(404)
    resultado = sync_stock()
    if resultado["error"]:
        flash(f"No se pudo sincronizar con STOCK: {resultado['error']}", "error")
    else:
        partes = []
        if resultado["nuevos"]:
            partes.append(f"{len(resultado['nuevos'])} vehículo(s) nuevo(s)")
        if resultado.get("vinculados"):
            partes.append(f"{len(resultado['vinculados'])} vinculado(s) a uno ya cargado a mano")
        if resultado["actualizados"]:
            partes.append(f"{len(resultado['actualizados'])} actualizado(s)")
        if not partes:
            partes.append("sin cambios")
        mensaje = "Sincronización con STOCK: " + ", ".join(partes) + "."
        if resultado["sin_ficha"]:
            mensaje += f" Carpetas sin ficha (ignoradas): {', '.join(resultado['sin_ficha'])}."
        flash(mensaje, "success")
    return redirect(url_for("stock.index"))


@bp.route("/")
def index():
    estado_filtro = request.args.get("estado", "todos")
    filtros = parsear_filtros(request.args)

    # Con algún filtro cargado, el buscador deja de depender de la pestaña:
    # busca en simultáneo Disponible + Por ingresar + En reparación + Red de
    # Agencieros y devuelve todo junto en una sola lista (pedido de Daniel
    # 15/09/2026, continuación 18). Sin filtros, se mantiene el browse
    # normal por pestaña de siempre (incluida Vendido, que el buscador
    # combinado no cubre a propósito).
    agencia_id = session["agencia_id"]
    if filtros:
        resultados = buscar_combinado(filtros, agencia_id)
        vehiculos = None
    else:
        resultados = None
        if estado_filtro in ESTADOS:
            vehiculos = query(
                "SELECT * FROM vehiculos WHERE agencia_id = ? AND estado = ? ORDER BY created_at DESC",
                (agencia_id, estado_filtro),
            )
        else:
            # "Todos" no incluye Vendido — solo se ve entrando puntualmente a
            # esa pestaña (pedido de Daniel 15/09/2026, continuación 19). El
            # buscador combinado (buscar_combinado, arriba) ya lo excluía.
            vehiculos = query(
                "SELECT * FROM vehiculos WHERE agencia_id = ? AND estado != 'vendido' ORDER BY created_at DESC",
                (agencia_id,),
            )

    conteos = {
        r["estado"]: r["c"]
        for r in query("SELECT estado, COUNT(*) c FROM vehiculos WHERE agencia_id = ? GROUP BY estado", (agencia_id,))
    }
    return render_template(
        "stock/index.html",
        vehiculos=vehiculos,
        resultados=resultados,
        estado_filtro=estado_filtro,
        estados=ESTADOS,
        estado_label=ESTADO_LABEL,
        conteos=conteos,
        filtros=filtros,
        mostrar_km=True,
        filtro_tab_nombre="estado",
        filtro_tab_valor=estado_filtro,
        limpiar_url=url_for("stock.index", estado=estado_filtro),
        foto_principal=foto_principal,
    )


@bp.route("/nuevo-por-foto", methods=["GET", "POST"])
def nuevo_por_foto():
    """Carga rápida: se saca una foto del título del vehículo y se leen de
    ahí los datos que trae (dominio, marca, modelo, año, motor, chasis) por
    OCR local (ver ocr_titulo.py) para precargar el alta de Stock, en vez de
    tipearlos a mano -- pedido de Daniel 16/09/2026. Kilómetros y color no
    están en el título y se completan a mano en el mismo formulario, igual
    que siempre. Ningún dato que no se pudo leer con confianza se completa
    solo -- queda en blanco para que se cargue a mano."""
    if request.method == "POST":
        archivo = request.files.get("foto_titulo")
        if not archivo or not archivo.filename:
            flash("Subí una foto del título para continuar.", "error")
            return redirect(url_for("stock.nuevo_por_foto"))
        ext = archivo.filename.rsplit(".", 1)[-1].lower() if "." in archivo.filename else ""
        if ext not in EXTENSIONES_PERMITIDAS:
            flash("Formato no soportado -- usá JPG, PNG, WEBP o GIF.", "error")
            return redirect(url_for("stock.nuevo_por_foto"))

        try:
            datos = extraer_datos_titulo(archivo.read(), catalogo=obtener_catalogo())
        except TesseractNoDisponible as e:
            flash(str(e), "error")
            return redirect(url_for("stock.nuevo_por_foto"))

        campos_clave = ["marca", "modelo", "anio", "dominio"]
        faltantes = [c for c in campos_clave if not datos.get(c)]
        if not datos["reconocidos"]:
            flash(
                "No se pudo leer ningún dato con confianza de esa foto (probá con más luz, "
                "más cerca y sin reflejos) -- se abrió el formulario en blanco para cargar a mano.",
                "error",
            )
        elif faltantes:
            flash(
                "Se completaron del título los datos que se pudieron leer con confianza. "
                f"Revisalos y completá a mano: {', '.join(faltantes)}, Kilómetros y Color.",
                "success",
            )
        else:
            flash(
                "Se completaron del título Marca, Modelo, Año y Dominio -- revisalos antes de "
                "guardar, y completá Kilómetros y Color a mano (no están en el título).",
                "success",
            )

        return redirect(url_for(
            "stock.nuevo",
            marca=datos.get("marca") or "",
            modelo=datos.get("modelo") or "",
            anio=datos.get("anio") or "",
            dominio=datos.get("dominio") or "",
            motor_detectado=datos.get("motor") or "",
            origen_carga="foto_titulo",
        ))

    return render_template("stock/nuevo_por_foto.html")


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    prefill = {
        "marca": request.args.get("marca", ""),
        "modelo": request.args.get("modelo", ""),
        "version": request.args.get("version", ""),
        "anio": request.args.get("anio", ""),
        "valor_publicado": request.args.get("precio_referencia", ""),
        # Los 3 de acá abajo solo llegan cargados desde el botón "Agregar a
        # Stock" de la Tasación (ver routes/tomas.py _url_agregar_a_stock):
        # el precio máximo recomendado como punto de partida de Valor de
        # compra, los gastos estimados ya calculados en la Toma/Tasación, y
        # un resumen de qué hay que reparar en Observaciones — para no
        # tener que volver a tipear a mano lo que ya se cargó en la Toma
        # técnica (pedido de Daniel 15/09/2026, continuación 29).
        "valor_compra": request.args.get("valor_compra", ""),
        "gastos": request.args.get("gastos", ""),
        "observaciones": request.args.get("observaciones", ""),
        # Resumen de Accesorios y equipamiento ya evaluados en la Toma
        # técnica (pedido de Daniel 16/09/2026) -- ver _texto_equipamiento
        # en routes/tomas.py.
        "equipamiento": request.args.get("equipamiento", ""),
        # Estos 5 solo llegan cargados desde "Cargar por foto del título"
        # (ver nuevo_por_foto abajo) -- Km y Color nunca vienen de ahí (no
        # están en el título) y quedan para completar a mano, igual que
        # siempre (pedido de Daniel 16/09/2026).
        "dominio": request.args.get("dominio", ""),
        "color": request.args.get("color", ""),
        "km": request.args.get("km", ""),
        "origen_carga": request.args.get("origen_carga", ""),
        "motor_detectado": request.args.get("motor_detectado", ""),
        # Solo llega si el alta vino del botón "Agregar a Stock" de la
        # Tasación (ver _url_agregar_a_stock en routes/tomas.py) -- permite
        # linkear de vuelta esa Toma a este vehículo una vez creado.
        "toma_id_origen": request.args.get("toma_id_origen", ""),
        # Solo llegan desde "¿Qué hacemos con la permuta?" (stock.permuta_destino):
        # el estado con el que ingresa y la operación de la que viene la permuta,
        # para registrar el destino una vez guardada la carga.
        "estado": request.args.get("estado", ""),
        "permuta_origen": request.args.get("permuta_origen", ""),
    }
    if request.method == "POST":
        f = request.form
        propiedad = f.get("propiedad", "propio")
        es_consignacion = propiedad == "consignacion"
        agencia_id = session["agencia_id"]
        vehiculo_id = execute(
            """INSERT INTO vehiculos
               (marca, modelo, version, anio, km, combustible, caja, color, dominio, estado,
                equipamiento, observaciones, documentacion, valor_compra, gastos, valor_publicado,
                fecha_ingreso, entrega_quien, fecha_ingreso_estimada,
                propiedad, consignante_nombre, consignante_telefono, agencia_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                f.get("marca"), f.get("modelo"), f.get("version"), f.get("anio") or None,
                f.get("km") or None, f.get("combustible"), f.get("caja"), f.get("color"),
                f.get("dominio"), f.get("estado", "disponible"), f.get("equipamiento"),
                f.get("observaciones"), f.get("documentacion"),
                float(f.get("valor_compra") or 0), float(f.get("gastos") or 0),
                float(f.get("valor_publicado") or 0), str(date.today()),
                f.get("entrega_quien") or None, f.get("fecha_ingreso_estimada") or None,
                propiedad,
                f.get("consignante_nombre") if es_consignacion else None,
                f.get("consignante_telefono") if es_consignacion else None,
                agencia_id,
            ),
        )

        # Módulo 3: aviso automático si hay un pedido de cliente que matchea
        # -- escopeado a la propia agencia (18/09/2026): Pedidos todavía no
        # está multi-tenant en sus rutas, pero esta consulta puntual no
        # puede mostrarle a una agencia el nombre de un cliente de otra.
        matches = query(
            """SELECT * FROM pedidos_clientes
               WHERE agencia_id = ? AND estado = 'buscando' AND marca = ? AND modelo = ?
                 AND (anio_desde IS NULL OR ? >= anio_desde)
                 AND (anio_hasta IS NULL OR ? <= anio_hasta)""",
            (agencia_id, f.get("marca"), f.get("modelo"), f.get("anio") or 0, f.get("anio") or 9999),
        )
        if matches:
            nombres = ", ".join(m["cliente_nombre"] for m in matches)
            flash(f"⚡ Este vehículo matchea con {len(matches)} pedido(s) del Banco de pedidos: {nombres}", "success")
        else:
            flash("Vehículo cargado en stock.", "success")

        # Si el alta vino de "Cargar por foto del título", se crea de una
        # vez una Toma vinculada a este vehículo con el checklist de 44
        # puntos ya armado (mismo checklist de Toma y Tasación de siempre,
        # sin duplicar nada) -- pedido de Daniel 16/09/2026.
        if f.get("origen_carga") == "foto_titulo":
            toma_id = execute(
                """INSERT INTO tomas_vehiculo (vehiculo_id, marca, modelo, version, anio, motor)
                   VALUES (?,?,?,?,?,?)""",
                (
                    vehiculo_id, f.get("marca"), f.get("modelo"), f.get("version"),
                    f.get("anio") or None, f.get("motor_detectado") or None,
                ),
            )
            flash(
                f"Se creó la Toma técnica #{toma_id} vinculada a este vehículo -- "
                "entrá a Toma y Tasación para completar el checklist de 44 puntos.",
                "success",
            )

        # Si el alta vino del botón "Agregar a Stock" de una Tasación (Toma
        # "suelta", sin vehículo todavía), se linkea esa Toma al vehículo
        # recién creado -- si no, quedaba huérfana para siempre y "Toma y
        # tasación" no tenía forma de saber que ya está en Stock (pedido de
        # Daniel 17/09/2026).
        if f.get("toma_id_origen"):
            execute(
                "UPDATE tomas_vehiculo SET vehiculo_id = ? WHERE id = ? AND vehiculo_id IS NULL",
                (vehiculo_id, f.get("toma_id_origen")),
            )

        # Si el alta es la de una permuta (viene de "¿Qué hacemos con la permuta?"):
        # se registra el destino y, si entra a reparación, se arranca el seguimiento.
        if f.get("permuta_origen"):
            destino_url = _registrar_ingreso_permuta(
                f.get("permuta_origen"), vehiculo_id, f.get("estado"), f.get("toma_id_origen"),
                {"marca": f.get("marca"), "modelo": f.get("modelo"), "version": f.get("version"), "anio": f.get("anio")},
            )
            if destino_url:
                return redirect(destino_url)

        return redirect(url_for("stock.detalle", vehiculo_id=vehiculo_id))

    origen, item_id = _parse_permuta_origen(prefill["permuta_origen"])
    return render_template(
        "stock/form.html", vehiculo=None, prefill=prefill, estados=ESTADOS, estado_label=ESTADO_LABEL,
        permuta_op=_permuta_operacion(origen, item_id) if origen else None,
    )


@bp.route("/<int:vehiculo_id>")
def detalle(vehiculo_id):
    vehiculo = query(
        "SELECT * FROM vehiculos WHERE id = ? AND agencia_id = ?", (vehiculo_id, session["agencia_id"]), one=True
    )
    if not vehiculo:
        flash("Vehículo no encontrado.", "error")
        return redirect(url_for("stock.index"))
    fotos = query("SELECT * FROM vehiculo_fotos WHERE vehiculo_id = ? ORDER BY orden, id", (vehiculo_id,))
    # Si este vehículo ya tiene una Toma vinculada (por OCR, o porque nació
    # de "Agregar a Stock" desde una Tasación), se muestra "Ver toma /
    # inspección" como referencia -- ya no se ofrece arrancar una Toma
    # nueva para un auto que ya está en Stock (pedido de Daniel 17/09/2026).
    toma_vinculada = query(
        "SELECT id FROM tomas_vehiculo WHERE vehiculo_id = ? ORDER BY id DESC LIMIT 1", (vehiculo_id,), one=True
    )
    # Operación de venta (19/09/2026): seña abierta / plan de Financiación en
    # trámite / cómo se cerró la venta -- ver bloque "Venta directa" arriba.
    venta_abierta = _venta_abierta(vehiculo_id) if vehiculo["estado"] == "senado" else None
    plan_pendiente = (
        _plan_pendiente(vehiculo_id) if vehiculo["estado"] == "senado" and not venta_abierta else None
    )
    venta_cerrada = plan_cierre = None
    if vehiculo["estado"] == "vendido":
        plan_cierre = query(
            """SELECT * FROM financiaciones WHERE vehiculo_id = ?
               AND estado NOT IN ('pendiente_firma', 'cancelado_reserva') ORDER BY id DESC LIMIT 1""",
            (vehiculo_id,), one=True,
        )
        if not plan_cierre:
            venta_cerrada = query(
                "SELECT * FROM ventas WHERE vehiculo_id = ? AND estado = 'cerrada' ORDER BY id DESC LIMIT 1",
                (vehiculo_id,), one=True,
            )
    # Permuta de la operación con la que se vendió: ¿ya se decidió qué hacer con ella?
    permuta_op = None
    origen_op = plan_cierre or venta_cerrada
    if origen_op and origen_op["permuta_marca"]:
        permuta_op = {
            "origen": "plan" if plan_cierre else "venta", "id": origen_op["id"],
            "destino": origen_op["permuta_destino"], "vehiculo_id": origen_op["permuta_vehiculo_id"],
            "desc": origen_op["permuta_descripcion"],
        }
    return render_template(
        "stock/detalle.html", vehiculo=vehiculo, rent=_rentabilidad(vehiculo), estado_label=ESTADO_LABEL, fotos=fotos,
        permuta_op=permuta_op,
        toma_vinculada=toma_vinculada, venta_abierta=venta_abierta, plan_pendiente=plan_pendiente,
        venta_cerrada=venta_cerrada, plan_cierre=plan_cierre, hoy=str(date.today()),
        tasaciones_permuta=(
            _tasaciones_para_permuta(session["agencia_id"]) if vehiculo["estado"] in ESTADOS_SENABLES else []
        ),
        precio_sugerido=_entero(vehiculo["valor_publicado"]),
        origenes_credito=_origenes_credito(session["agencia_id"]),
    )


@bp.route("/<int:vehiculo_id>/fotos", methods=["POST"])
def subir_fotos(vehiculo_id):
    vehiculo = query(
        "SELECT * FROM vehiculos WHERE id = ? AND agencia_id = ?", (vehiculo_id, session["agencia_id"]), one=True
    )
    if not vehiculo:
        flash("Vehículo no encontrado.", "error")
        return redirect(url_for("stock.index"))

    archivos = [a for a in request.files.getlist("fotos") if a and a.filename]
    if not archivos:
        flash("Elegí al menos una foto para subir.", "error")
        return redirect(url_for("stock.detalle", vehiculo_id=vehiculo_id))

    orden_actual = query(
        "SELECT COALESCE(MAX(orden), -1) o FROM vehiculo_fotos WHERE vehiculo_id = ?", (vehiculo_id,), one=True
    )["o"]
    carpeta = uploads_dir("vehiculos", str(vehiculo_id))
    os.makedirs(carpeta, exist_ok=True)

    subidas, rechazadas = 0, 0
    for archivo in archivos:
        ext = archivo.filename.rsplit(".", 1)[-1].lower() if "." in archivo.filename else ""
        if ext not in EXTENSIONES_PERMITIDAS:
            rechazadas += 1
            continue
        orden_actual += 1
        nombre_archivo = f"{uuid.uuid4().hex}.{ext}"
        archivo.save(os.path.join(carpeta, nombre_archivo))
        url = url_for("static", filename=f"uploads/vehiculos/{vehiculo_id}/{nombre_archivo}")
        execute(
            "INSERT INTO vehiculo_fotos (vehiculo_id, url, orden) VALUES (?,?,?)",
            (vehiculo_id, url, orden_actual),
        )
        subidas += 1

    if subidas:
        mensaje = f"{subidas} foto(s) agregada(s)."
        if rechazadas:
            mensaje += f" {rechazadas} archivo(s) con formato no soportado fueron ignorados."
        flash(mensaje, "success")
    else:
        flash("Ninguna foto se pudo subir (formato no soportado — usá JPG, PNG, WEBP o GIF).", "error")
    return redirect(url_for("stock.detalle", vehiculo_id=vehiculo_id))


@bp.route("/<int:vehiculo_id>/fotos/<int:foto_id>/eliminar", methods=["POST"])
def eliminar_foto(vehiculo_id, foto_id):
    vehiculo = query(
        "SELECT id FROM vehiculos WHERE id = ? AND agencia_id = ?", (vehiculo_id, session["agencia_id"]), one=True
    )
    if not vehiculo:
        flash("Vehículo no encontrado.", "error")
        return redirect(url_for("stock.index"))
    foto = query(
        "SELECT * FROM vehiculo_fotos WHERE id = ? AND vehiculo_id = ?", (foto_id, vehiculo_id), one=True
    )
    if foto:
        execute("DELETE FROM vehiculo_fotos WHERE id = ?", (foto_id,))
        # La URL guardada es "/static/uploads/vehiculos/<id>/<archivo>"; la
        # parte fisica puede vivir en el volumen de Railway (storage.uploads_dir()),
        # no necesariamente bajo static/ del codigo -- por eso no se usa
        # root_path acá, sino el mismo helper que se usa al guardarlas.
        relativo = foto["url"].split("uploads/", 1)[-1]
        ruta_local = uploads_dir(relativo)
        try:
            if os.path.isfile(ruta_local):
                os.remove(ruta_local)
        except OSError:
            pass
        flash("Foto eliminada.", "success")
    return redirect(url_for("stock.detalle", vehiculo_id=vehiculo_id))


@bp.route("/<int:vehiculo_id>/editar", methods=["GET", "POST"])
def editar(vehiculo_id):
    vehiculo = query(
        "SELECT * FROM vehiculos WHERE id = ? AND agencia_id = ?", (vehiculo_id, session["agencia_id"]), one=True
    )
    if not vehiculo:
        flash("Vehículo no encontrado.", "error")
        return redirect(url_for("stock.index"))

    if request.method == "POST":
        f = request.form
        fecha_venta = str(date.today()) if f.get("estado") == "vendido" and vehiculo["estado"] != "vendido" else vehiculo["fecha_venta"]
        propiedad = f.get("propiedad", "propio")
        es_consignacion = propiedad == "consignacion"
        if vehiculo["estado"] == "senado" and f.get("estado") != "senado":
            # Si se cambia a mano el estado de un auto señado desde acá, la
            # seña abierta de "Venta directa" no puede quedar colgada.
            execute(
                "UPDATE ventas SET estado = 'cancelada' WHERE vehiculo_id = ? AND estado = 'senado'",
                (vehiculo_id,),
            )
        execute(
            """UPDATE vehiculos SET marca=?, modelo=?, version=?, anio=?, km=?, combustible=?, caja=?,
               color=?, dominio=?, estado=?, equipamiento=?, observaciones=?, documentacion=?,
               valor_compra=?, gastos=?, valor_publicado=?, valor_vendido=?, fecha_venta=?,
               entrega_quien=?, fecha_ingreso_estimada=?,
               propiedad=?, consignante_nombre=?, consignante_telefono=?,
               updated_at=datetime('now')
               WHERE id=?""",
            (
                f.get("marca"), f.get("modelo"), f.get("version"), f.get("anio") or None,
                f.get("km") or None, f.get("combustible"), f.get("caja"), f.get("color"),
                f.get("dominio"), f.get("estado"), f.get("equipamiento"), f.get("observaciones"),
                f.get("documentacion"), float(f.get("valor_compra") or 0), float(f.get("gastos") or 0),
                float(f.get("valor_publicado") or 0),
                float(f.get("valor_vendido")) if f.get("valor_vendido") else None,
                fecha_venta,
                f.get("entrega_quien") or None, f.get("fecha_ingreso_estimada") or None,
                propiedad,
                f.get("consignante_nombre") if es_consignacion else None,
                f.get("consignante_telefono") if es_consignacion else None,
                vehiculo_id,
            ),
        )
        flash("Vehículo actualizado.", "success")
        return redirect(url_for("stock.detalle", vehiculo_id=vehiculo_id))

    return render_template("stock/form.html", vehiculo=vehiculo, prefill=None, estados=ESTADOS, estado_label=ESTADO_LABEL)


# ---------------------------------------------------------------------
# Venta directa desde Stock, SIN financiación (19/09/2026, pedido de
# Daniel). Dos pasos, los dos opcionales entre sí:
#   1) "Señar": se recibe una seña -> el vehículo pasa a "Señado" y se
#      crea una fila en `ventas` (estado 'senado') con cliente y seña.
#   2) "Cerrar venta": precio, permuta opcional y efectivo cobrado ->
#      el vehículo pasa a "Vendido" y la fila queda 'cerrada'. También
#      se puede cerrar directo, sin seña previa (venta de contado).
# Regla de oro: el efectivo cobrado es el TOTAL que entró, con la seña
# ADENTRO (la seña es solo la parte que llegó antes, nunca se suma
# aparte). Sin financiación la cuenta tiene que cerrar exacta:
#   precio de venta = permuta + efectivo cobrado.
# Si queda saldo para pagar en cuotas, la venta va por Financiación.
# ---------------------------------------------------------------------
ESTADOS_SENABLES = ("disponible", "por_ingresar", "en_reparacion")


def _vehiculo_propio(vehiculo_id):
    return query(
        "SELECT * FROM vehiculos WHERE id = ? AND agencia_id = ?",
        (vehiculo_id, session["agencia_id"]), one=True,
    )


def _venta_abierta(vehiculo_id):
    return query(
        "SELECT * FROM ventas WHERE vehiculo_id = ? AND estado = 'senado' ORDER BY id DESC LIMIT 1",
        (vehiculo_id,), one=True,
    )


def _plan_pendiente(vehiculo_id):
    return query(
        """SELECT id, cliente_nombre FROM financiaciones
           WHERE vehiculo_id = ? AND estado = 'pendiente_firma' ORDER BY id DESC LIMIT 1""",
        (vehiculo_id,), one=True,
    )


def _tasaciones_para_permuta(agencia_id, incluir_id=None):
    """Tasaciones de esta agencia que se pueden ofrecer como permuta:
    las que todavía no se usaron en un crédito ni en otra venta (más la
    que ya tenía elegida esta misma operación, si la tuviera)."""
    return query(
        """SELECT * FROM tasaciones
           WHERE agencia_id = ? AND (
               (id NOT IN (SELECT permuta_tasacion_id FROM financiaciones WHERE permuta_tasacion_id IS NOT NULL)
                AND id NOT IN (SELECT permuta_tasacion_id FROM ventas
                               WHERE permuta_tasacion_id IS NOT NULL AND estado IN ('senado', 'cerrada')))
               OR id = ?)
           ORDER BY created_at DESC""",
        (agencia_id, incluir_id or 0),
    )


def _numero(valor, default=None):
    try:
        return float(valor) if valor not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _pesos(n):
    return "$" + "{:,.0f}".format(n or 0).replace(",", ".")


def _entero(valor):
    """Número para mostrar en un <input type="number">: sin el ".0" que
    el navegador en español muestra como "14800000,0" cuando llega un float."""
    if valor in (None, "", 0):
        return ""
    try:
        return int(valor) if float(valor) == int(float(valor)) else valor
    except (TypeError, ValueError):
        return valor


def _leer_permuta_sena(f, tasaciones):
    """Permuta prevista al señar -> (datos, error). Sin tildar "va a entregar
    un vehículo en permuta" -> (None, None). Si se elige una tasación ya
    hecha, Marca/Modelo/Versión/Año salen de ella; si no está tasado, hay
    que cargar como mínimo Año, Marca y Modelo (Versión y Km si se saben)
    para poder cruzarlo con los pedidos. El valor de toma es opcional acá:
    se define al cerrar la venta."""
    if not f.get("permuta_hay"):
        return None, None
    try:
        elegido = int(f.get("permuta_tasacion_id")) if f.get("permuta_tasacion_id") else None
    except ValueError:
        elegido = None
    t = next((t for t in tasaciones if t["id"] == elegido), None) if elegido else None
    if t:
        marca, modelo, version, anio = t["marca"], t["modelo"], t["version"], t["anio"]
        valor = _numero(f.get("permuta_valor")) or t["precio_max_recomendado"] or None
    else:
        marca = (f.get("permuta_marca") or "").strip() or None
        modelo = (f.get("permuta_modelo") or "").strip() or None
        version = (f.get("permuta_version") or "").strip() or None
        try:
            anio = int(f.get("permuta_anio")) if f.get("permuta_anio") else None
        except ValueError:
            anio = None
        valor = _numero(f.get("permuta_valor")) or None
    if not (marca and modelo and anio):
        return None, ("Para la permuta cargá como mínimo Año, Marca y Modelo (o elegí una tasación ya hecha): "
                      "con eso se cruza con los pedidos.")
    try:
        km = int(float(f.get("permuta_km"))) if f.get("permuta_km") else None
    except ValueError:
        km = None
    return {
        "marca": marca, "modelo": modelo, "version": version, "anio": anio, "km": km, "valor": valor,
        "tasacion_id": t["id"] if t else None,
        "desc": " ".join(str(p) for p in (marca, modelo, version, anio) if p),
    }, None


# ---------------------------------------------------------------------------
# Destino de la permuta una vez cerrada la operación (19/09/2026, pedido de Daniel):
# el vehículo sigue como "Posible entrega" (matchea con pedidos) hasta que se decide
# si ingresa a Stock (se completa la carga) o va a reparación (arranca el seguimiento).
# ---------------------------------------------------------------------------
DESTINO_PERMUTA_LABEL = {
    "stock": "Ingresó a Stock",
    "reparacion": "Ingresó a reparación",
    "no_ingresa": "No ingresó a Stock",
}


def _parse_permuta_origen(token):
    try:
        origen, item_id = (token or "").split(":")
        return (origen, int(item_id)) if origen in ("venta", "plan") else (None, None)
    except ValueError:
        return None, None


def _permuta_operacion(origen, item_id):
    """Operación ya cerrada (venta directa o plan de Financiación activo/finalizado)
    de esta agencia que trae una permuta con datos estructurados. None si no existe,
    es de otra agencia, todavía no se cerró o no tiene permuta."""
    agencia = session["agencia_id"]
    if origen == "venta":
        fila = query("SELECT * FROM ventas WHERE id = ? AND agencia_id = ? AND estado = 'cerrada'",
                     (item_id, agencia), one=True)
        tabla = "ventas"
    elif origen == "plan":
        fila = query("""SELECT * FROM financiaciones WHERE id = ? AND COALESCE(agencia_id, 1) = ?
                        AND estado IN ('activo', 'finalizado')""", (item_id, agencia), one=True)
        tabla = "financiaciones"
    else:
        return None
    if not fila or not fila["permuta_marca"]:
        return None
    vendido = query("SELECT id, marca, modelo, version, anio FROM vehiculos WHERE id = ?",
                    (fila["vehiculo_id"],), one=True) if fila["vehiculo_id"] else None
    return {
        "origen": origen, "id": item_id, "tabla": tabla, "fila": fila, "cliente": fila["cliente_nombre"],
        "vendido": vendido, "destino": fila["permuta_destino"], "vehiculo_ingresado": fila["permuta_vehiculo_id"],
    }


def _permutas_pendientes(agencia_id):
    """Permutas de operaciones ya cerradas que todavía esperan destino."""
    filas = []
    for r in query(
        """SELECT vt.id, vt.cliente_nombre, vt.permuta_descripcion, vt.permuta_km, vt.permuta_valor,
                  vt.fecha_venta AS fecha, v.marca AS v_marca, v.modelo AS v_modelo, v.version AS v_version, v.anio AS v_anio
           FROM ventas vt LEFT JOIN vehiculos v ON v.id = vt.vehiculo_id
           WHERE vt.agencia_id = ? AND vt.estado = 'cerrada' AND vt.permuta_marca IS NOT NULL
                 AND vt.permuta_marca != '' AND vt.permuta_destino IS NULL""", (agencia_id,)):
        filas.append(dict(r, origen="venta"))
    for r in query(
        """SELECT f.id, f.cliente_nombre, f.permuta_descripcion, f.permuta_km, f.permuta_valor,
                  COALESCE(v.fecha_venta, substr(f.created_at, 1, 10)) AS fecha,
                  v.marca AS v_marca, v.modelo AS v_modelo, v.version AS v_version, v.anio AS v_anio
           FROM financiaciones f LEFT JOIN vehiculos v ON v.id = f.vehiculo_id
           WHERE COALESCE(f.agencia_id, 1) = ? AND f.estado IN ('activo', 'finalizado') AND f.permuta_marca IS NOT NULL
                 AND f.permuta_marca != '' AND f.permuta_destino IS NULL""", (agencia_id,)):
        filas.append(dict(r, origen="plan"))
    filas.sort(key=lambda x: (x["fecha"] or "", x["id"]), reverse=True)
    return filas


def _url_alta_permuta(op, estado):
    """Alta en Stock precargada con la permuta: si vino de una Tasación con Toma, con
    todo lo ya cargado ahí (reparaciones, equipamiento, gastos); si no, con los datos
    mínimos. El valor de compra es el precio de toma pactado en la operación."""
    fila = op["fila"]
    params = {}
    if fila["permuta_tasacion_id"]:
        t = query("SELECT toma_id FROM tasaciones WHERE id = ?", (fila["permuta_tasacion_id"],), one=True)
        if t and t["toma_id"]:
            from routes.tomas import datos_alta_stock_de_toma
            params = datos_alta_stock_de_toma(t["toma_id"]) or {}
    nota = f"Ingresó como permuta de la venta a {op['cliente'] or 'cliente sin nombre'}."
    previas = params.get("observaciones")
    params.update({
        "marca": fila["permuta_marca"], "modelo": fila["permuta_modelo"], "version": fila["permuta_version"],
        "anio": fila["permuta_anio"], "km": fila["permuta_km"],
        "valor_compra": _entero(fila["permuta_valor"]),
        "observaciones": nota + ("\n" + previas if previas else ""),
        "estado": estado, "permuta_origen": f"{op['origen']}:{op['id']}",
    })
    return url_for("stock.nuevo", **{k: v for k, v in params.items() if v not in (None, "")})


def _registrar_ingreso_permuta(token, vehiculo_id, estado_final, toma_id_origen, datos):
    """Se guardó el alta de una permuta: queda registrado el destino en la operación (deja
    de ser "Posible entrega": ya es un vehículo de Stock). Si entra a reparación devuelve
    la URL del seguimiento (Toma técnica); si no, None."""
    origen, item_id = _parse_permuta_origen(token)
    op = _permuta_operacion(origen, item_id) if origen else None
    if not op or op["destino"] is not None:
        return None
    destino = "reparacion" if estado_final == "en_reparacion" else "stock"
    execute(
        f"UPDATE {op['tabla']} SET permuta_destino = ?, permuta_vehiculo_id = ?, permuta_destino_fecha = ? WHERE id = ?",
        (destino, vehiculo_id, str(date.today()), item_id),
    )
    if destino == "stock":
        flash("La permuta quedó registrada como ingresada a Stock.", "success")
        return None
    flash("La permuta ingresó a reparación. Arrancá el seguimiento: la Toma técnica (checklist de 44 puntos con "
          "el costo de cada reparación) y después la inspección de chapa.", "success")
    if toma_id_origen:
        try:
            return url_for("tomas.detalle", toma_id=int(toma_id_origen))
        except ValueError:
            pass
    return url_for("tomas.nueva", vehiculo_id=vehiculo_id, marca=datos.get("marca") or "", modelo=datos.get("modelo") or "",
                   version=datos.get("version") or "", anio=datos.get("anio") or "")


@bp.route("/permutas")
def permutas():
    """Permutas de ventas ya cerradas que todavía esperan destino."""
    return render_template("stock/permutas.html", permutas=_permutas_pendientes(session["agencia_id"]))


@bp.route("/permuta/<origen>/<int:item_id>")
def permuta_destino(origen, item_id):
    """¿Qué hacemos con el vehículo que entró en permuta?: ingresa a Stock (se completa la
    carga) o va a reparación (se arranca el seguimiento). Mientras tanto sigue como
    "Posible entrega" para los matches."""
    op = _permuta_operacion(origen, item_id)
    if not op:
        flash("No encontré esa permuta (o la operación todavía no se cerró).", "error")
        return redirect(url_for("stock.index"))
    fila = op["fila"]
    propios, red = ([], [])
    if op["destino"] is None:
        from routes.pedidos import _buscar_matches_permuta
        propios, red = _buscar_matches_permuta(session["agencia_id"], fila["permuta_marca"], fila["permuta_modelo"])
    ingresado = query("SELECT id, marca, modelo, version, anio, estado FROM vehiculos WHERE id = ?",
                      (op["vehiculo_ingresado"],), one=True) if op["vehiculo_ingresado"] else None
    return render_template(
        "stock/permuta_destino.html", op=op, fila=fila, propios=propios, red=red, ingresado=ingresado,
        destino_label=DESTINO_PERMUTA_LABEL,
        url_stock=_url_alta_permuta(op, "disponible") if op["destino"] is None else None,
        url_reparacion=_url_alta_permuta(op, "en_reparacion") if op["destino"] is None else None,
    )


@bp.route("/permuta/<origen>/<int:item_id>/no-ingresa", methods=["POST"])
def permuta_no_ingresa(origen, item_id):
    """La permuta no va a entrar a Stock (ya estaba cargada, no llegó, se vendió afuera):
    sale de "Posible entrega" y deja de figurar como pendiente."""
    op = _permuta_operacion(origen, item_id)
    if not op or op["destino"] is not None:
        flash("Esa permuta ya no está pendiente.", "error")
        return redirect(url_for("stock.permutas"))
    execute(
        f"UPDATE {op['tabla']} SET permuta_destino = 'no_ingresa', permuta_destino_fecha = ? WHERE id = ?",
        (str(date.today()), item_id),
    )
    flash("Listo: la permuta quedó marcada como que no ingresa a Stock y dejó de ofrecerse para los matches.", "success")
    return redirect(url_for("stock.permutas"))


ORIGENES_CREDITO_BASE = ["Banco", "Financiera", "Prendario"]


def _origenes_credito(agencia_id):
    """Sugerencias para "de dónde viene el crédito": primero los que esta
    agencia ya usó (los más frecuentes arriba) y después algunos genéricos."""
    usados = [
        r["credito_origen"] for r in query(
            """SELECT credito_origen, COUNT(*) n FROM ventas
               WHERE agencia_id = ? AND credito_origen IS NOT NULL AND credito_origen != ''
               GROUP BY credito_origen ORDER BY n DESC, credito_origen""",
            (agencia_id,),
        )
    ]
    return usados + [o for o in ORIGENES_CREDITO_BASE if o not in usados]


def _leer_credito(f):
    """Crédito externo del formulario (seña o cierre) -> (origen, monto, error).
    Sin tildar "parte del saldo con un crédito" no hay crédito. Si se tilda,
    hay que decir de dónde viene (banco, financiera...) y por qué monto."""
    if not f.get("credito_hay"):
        return None, None, None
    origen = (f.get("credito_origen") or "").strip()
    monto = _numero(f.get("credito_monto"), 0)
    if not origen or monto <= 0:
        return None, None, ("Si parte del saldo se completa con un crédito externo, cargá de dónde viene "
                            "(banco, financiera...) y por qué monto.")
    return origen, monto, None


@bp.route("/<int:vehiculo_id>/senar", methods=["POST"])
def senar(vehiculo_id):
    vehiculo = _vehiculo_propio(vehiculo_id)
    if not vehiculo:
        flash("Vehículo no encontrado.", "error")
        return redirect(url_for("stock.index"))
    if vehiculo["estado"] not in ESTADOS_SENABLES:
        flash("Este vehículo ya está señado o vendido.", "error")
        return redirect(url_for("stock.detalle", vehiculo_id=vehiculo_id))

    f = request.form
    cliente = (f.get("cliente_nombre") or "").strip()
    sena = _numero(f.get("sena"), 0)
    precio = _numero(f.get("precio_venta"))
    # Una seña SIEMPRE es en efectivo (Daniel 19/09/2026): nadie deja un
    # vehículo antes de cerrar la operación. La permuta, si la hay, es solo
    # la previsión de que va a entrar un vehículo: se piden sus datos
    # mínimos para tenerlo presente en los matches ("Posible entrega").
    permuta, error_permuta = _leer_permuta_sena(f, _tasaciones_para_permuta(session["agencia_id"]))
    valor_permuta = (permuta or {}).get("valor") or 0
    # Crédito externo (Daniel 19/09/2026): el saldo puede ir todo en efectivo o
    # una parte con un crédito de un banco/financiera. Se anota de dónde viene
    # y por cuánto; al cerrar la venta se precarga.
    credito_origen, credito_monto, error_credito = _leer_credito(f)
    credito = credito_monto or 0
    error = None
    if not cliente:
        error = "Cargá el nombre de quien deja la seña."
    elif sena <= 0:
        error = "Cargá el monto de la seña en efectivo (mayor a 0)."
    elif error_permuta:
        error = error_permuta
    elif error_credito:
        error = error_credito
    elif credito and not precio:
        error = "Para registrar un crédito cargá también el precio acordado: con él se calcula cuánto queda en efectivo."
    elif precio and sena + valor_permuta + credito > precio + 0.5:
        error = ("La seña en efectivo + la permuta + el crédito superan el precio acordado. Revisá los montos."
                 if credito else "La seña en efectivo + la permuta superan el precio acordado. Revisá los montos.")
    if error:
        flash(error, "error")
        return redirect(url_for("stock.detalle", vehiculo_id=vehiculo_id))

    hoy = str(date.today())
    p = permuta or {}
    execute(
        """INSERT INTO ventas (agencia_id, vehiculo_id, estado, estado_previo, cliente_nombre,
                               cliente_telefono, precio_venta, sena, fecha_sena, permuta_tasacion_id,
                               permuta_valor, permuta_descripcion, permuta_marca, permuta_modelo,
                               permuta_version, permuta_anio, permuta_km, observaciones,
                               credito_origen, credito_monto)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            session["agencia_id"], vehiculo_id, "senado", vehiculo["estado"], cliente,
            (f.get("cliente_telefono") or "").strip() or None, precio, sena, hoy,
            p.get("tasacion_id"), p.get("valor"), p.get("desc"), p.get("marca"), p.get("modelo"),
            p.get("version"), p.get("anio"), p.get("km"),
            (f.get("observaciones") or "").strip() or None,
            credito_origen, credito_monto,
        ),
    )
    execute(
        "UPDATE vehiculos SET estado = 'senado', updated_at = datetime('now') WHERE id = ? AND agencia_id = ?",
        (vehiculo_id, session["agencia_id"]),
    )
    mensaje = f"Seña de {_pesos(sena)} registrada"
    if permuta:
        mensaje += f" — permuta prevista: {permuta['desc']}"
    if credito_monto:
        mensaje += f" — crédito de {credito_origen} por {_pesos(credito_monto)}"
    flash(mensaje + " — el vehículo queda Señado.", "success")
    if permuta:
        # ¿Ese vehículo ya tiene comprador? Mismo cruce que al cargar un pedido con permuta.
        from routes.pedidos import _buscar_matches_permuta
        propios, red = _buscar_matches_permuta(session["agencia_id"], permuta["marca"], permuta["modelo"])
        partes = []
        if propios:
            partes.append(f"{len(propios)} pedido(s) propio(s)")
        if red:
            partes.append(f"{len(red)} publicación(es) de la Red")
        if partes:
            flash("⚡ La permuta ya tiene comprador: matchea con " + " y ".join(partes) + ".", "success")
    return redirect(url_for("stock.detalle", vehiculo_id=vehiculo_id))


@bp.route("/<int:vehiculo_id>/senar/cancelar", methods=["POST"])
def cancelar_sena(vehiculo_id):
    vehiculo = _vehiculo_propio(vehiculo_id)
    if not vehiculo:
        flash("Vehículo no encontrado.", "error")
        return redirect(url_for("stock.index"))
    venta = _venta_abierta(vehiculo_id) if vehiculo["estado"] == "senado" else None
    if not venta:
        flash("Este vehículo no tiene una seña abierta para cancelar.", "error")
        return redirect(url_for("stock.detalle", vehiculo_id=vehiculo_id))

    nota = f"[Seña cancelada {date.today()}] Seña recibida: {_pesos(venta['sena'])} -- a definir si se devuelve."
    observaciones = f"{venta['observaciones']}\n{nota}" if venta["observaciones"] else nota
    execute(
        "UPDATE ventas SET estado = 'cancelada', observaciones = ? WHERE id = ?",
        (observaciones, venta["id"]),
    )
    execute(
        "UPDATE vehiculos SET estado = ?, updated_at = datetime('now') WHERE id = ? AND agencia_id = ?",
        (venta["estado_previo"] or "disponible", vehiculo_id, session["agencia_id"]),
    )
    flash("Seña cancelada — el vehículo vuelve a estar a la venta. La seña quedó en \"Señas por resolver\" del Dashboard para que decidas si la retenés o la devolvés.", "success")
    return redirect(url_for("stock.detalle", vehiculo_id=vehiculo_id))


@bp.route("/<int:vehiculo_id>/vender", methods=["GET", "POST"])
def vender(vehiculo_id):
    vehiculo = _vehiculo_propio(vehiculo_id)
    if not vehiculo:
        flash("Vehículo no encontrado.", "error")
        return redirect(url_for("stock.index"))
    if vehiculo["estado"] == "vendido":
        flash("Este vehículo ya figura como vendido.", "error")
        return redirect(url_for("stock.detalle", vehiculo_id=vehiculo_id))
    plan = _plan_pendiente(vehiculo_id)
    if plan:
        flash(
            "Este vehículo está señado por un crédito de Financiación en trámite -- "
            "cerrá o cancelá esa operación desde Financiación.",
            "error",
        )
        return redirect(url_for("stock.detalle", vehiculo_id=vehiculo_id))

    venta = _venta_abierta(vehiculo_id) if vehiculo["estado"] == "senado" else None
    tasaciones = _tasaciones_para_permuta(
        session["agencia_id"], venta["permuta_tasacion_id"] if venta else None
    )

    def render(datos):
        return render_template(
            "stock/vender.html", vehiculo=vehiculo, venta=venta, tasaciones=tasaciones,
            datos=datos, estado_label=ESTADO_LABEL,
            origenes_credito=_origenes_credito(session["agencia_id"]),
        )

    if request.method == "GET":
        return render({
            "cliente_nombre": (venta["cliente_nombre"] if venta else "") or "",
            "cliente_telefono": (venta["cliente_telefono"] if venta else "") or "",
            "precio_venta": _entero((venta["precio_venta"] if venta and venta["precio_venta"] else vehiculo["valor_publicado"]) or 0),
            "fecha_venta": str(date.today()),
            "permuta_hay": "1" if venta and (venta["permuta_marca"] or venta["permuta_valor"]) else "",
            "permuta_tasacion_id": (venta["permuta_tasacion_id"] if venta else None) or "",
            "permuta_descripcion": (venta["permuta_descripcion"] if venta else "") or "",
            "permuta_valor": _entero(venta["permuta_valor"]) if venta else "",
            # Datos estructurados de la permuta prevista al señar (Año/Marca/Modelo/Versión/Km).
            "permuta_marca": (venta["permuta_marca"] if venta else "") or "",
            "permuta_modelo": (venta["permuta_modelo"] if venta else "") or "",
            "permuta_version": (venta["permuta_version"] if venta else "") or "",
            "permuta_anio": (venta["permuta_anio"] if venta else "") or "",
            "permuta_km": _entero(venta["permuta_km"]) if venta else "",
            "credito_hay": "1" if venta and venta["credito_monto"] else "",
            "credito_origen": (venta["credito_origen"] if venta else "") or "",
            "credito_monto": _entero(venta["credito_monto"]) if venta else "",
        })

    f = request.form
    datos = dict(f.items())
    cliente = (f.get("cliente_nombre") or "").strip()
    precio = _numero(f.get("precio_venta"), 0)
    hay_permuta = bool(f.get("permuta_hay"))
    # Permuta estructurada (Año/Marca/Modelo o tasación): así el vehículo que entra queda
    # cargado para los matches y para precargar el alta en Stock (ver permuta_destino).
    permuta, error_permuta = _leer_permuta_sena(f, tasaciones)
    permuta = permuta or {}
    permuta_valor = permuta.get("valor") or 0
    permuta_desc = permuta.get("desc")
    permuta_tasacion_id = permuta.get("tasacion_id")
    credito_origen, credito_monto, error_credito = _leer_credito(f)
    credito = credito_monto or 0
    efectivo = _numero(f.get("efectivo_cobrado"))
    if efectivo is None:
        efectivo = max(precio - permuta_valor - credito, 0)
    sena = venta["sena"] if venta else _numero(f.get("sena"), 0)
    try:
        fecha_venta = str(date.fromisoformat((f.get("fecha_venta") or "")[:10]))
    except ValueError:
        fecha_venta = str(date.today())

    errores = []
    if not cliente:
        errores.append("Cargá el nombre del comprador.")
    if precio <= 0:
        errores.append("Cargá el precio de venta.")
    if hay_permuta and error_permuta:
        errores.append(error_permuta)
    elif hay_permuta and permuta_valor <= 0:
        errores.append("Cargá el precio de toma de la permuta (o desmarcá \"Hay un vehículo en permuta\").")
    if error_credito:
        errores.append(error_credito)
    if sena and sena > efectivo + 0.5:
        errores.append("La seña no puede ser mayor que el efectivo cobrado: la seña ya está incluida en el efectivo.")
    diferencia = round(precio - permuta_valor - credito - efectivo, 2)
    if precio > 0 and abs(diferencia) > 0.5:
        if diferencia > 0:
            errores.append(
                f"Faltan {_pesos(diferencia)} para completar el precio (precio − permuta − crédito externo − efectivo cobrado). "
                "Si ese saldo va con un crédito de un banco o financiera, tildá \"crédito externo\" y cargá de dónde viene y por cuánto; "
                "si lo va a pagar en cuotas propias, cerrá la venta desde Financiación; "
                "si hubo un descuento, bajá el precio de venta."
            )
        else:
            errores.append(
                f"El efectivo cobrado + la permuta + el crédito superan el precio de venta en {_pesos(-diferencia)}. Revisá los montos."
            )
    if errores:
        for e in errores:
            flash(e, "error")
        return render(datos)

    telefono = (f.get("cliente_telefono") or "").strip() or None
    if venta:
        execute(
            """UPDATE ventas SET estado = 'cerrada', cliente_nombre = ?, cliente_telefono = ?,
                   precio_venta = ?, permuta_tasacion_id = ?, permuta_valor = ?, permuta_descripcion = ?,
                   permuta_marca = ?, permuta_modelo = ?, permuta_version = ?, permuta_anio = ?, permuta_km = ?,
                   efectivo_cobrado = ?, fecha_venta = ?, credito_origen = ?, credito_monto = ? WHERE id = ?""",
            (cliente, telefono, precio, permuta_tasacion_id, permuta_valor or None, permuta_desc,
             permuta.get("marca"), permuta.get("modelo"), permuta.get("version"), permuta.get("anio"), permuta.get("km"),
             efectivo, fecha_venta, credito_origen, credito_monto, venta["id"]),
        )
        venta_id = venta["id"]
    else:
        venta_id = execute(
            """INSERT INTO ventas (agencia_id, vehiculo_id, estado, estado_previo, cliente_nombre,
                                   cliente_telefono, precio_venta, sena, fecha_sena, permuta_tasacion_id,
                                   permuta_valor, permuta_descripcion, permuta_marca, permuta_modelo,
                                   permuta_version, permuta_anio, permuta_km, efectivo_cobrado, fecha_venta,
                                   credito_origen, credito_monto)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (session["agencia_id"], vehiculo_id, "cerrada", vehiculo["estado"], cliente, telefono,
             precio, sena or 0, fecha_venta if sena else None, permuta_tasacion_id,
             permuta_valor or None, permuta_desc, permuta.get("marca"), permuta.get("modelo"), permuta.get("version"),
             permuta.get("anio"), permuta.get("km"), efectivo, fecha_venta, credito_origen, credito_monto),
        )

    execute(
        """UPDATE vehiculos SET estado = 'vendido', valor_vendido = ?, fecha_venta = ?,
               updated_at = datetime('now') WHERE id = ? AND agencia_id = ?""",
        (precio, fecha_venta, vehiculo_id, session["agencia_id"]),
    )
    mensaje = f"Venta cerrada — {_pesos(precio)}: {_pesos(efectivo)} en efectivo"
    if sena:
        mensaje += f" (con la seña de {_pesos(sena)} adentro)"
    if credito_monto:
        mensaje += f" + crédito de {credito_origen} por {_pesos(credito_monto)}"
    if permuta_valor:
        mensaje += f" + permuta por {_pesos(permuta_valor)}"
    flash(mensaje + ". El vehículo pasa a Vendido.", "success")
    if permuta.get("marca"):
        # El vehículo de la permuta sigue disponible para matchear ("Posible entrega")
        # hasta que se decida qué hacer con él.
        return redirect(url_for("stock.permuta_destino", origen="venta", item_id=venta_id))
    return redirect(url_for("stock.detalle", vehiculo_id=vehiculo_id))


@bp.route("/<int:vehiculo_id>/ficha")
def ficha(vehiculo_id):
    """Ficha comercial para compartir por WhatsApp o subir a una historia --
    solo datos de cara al comprador (precio, financiación, equipamiento,
    fotos), nunca costo/ganancia/consignante. Ruta pública (ver `_require_login`
    en app.py): quien la recibe no tiene login en la app (pedido de Daniel
    16/09/2026: "que se pueda compartir en historias o por WhatsApp")."""
    vehiculo = query("SELECT * FROM vehiculos WHERE id = ?", (vehiculo_id,), one=True)
    if not vehiculo:
        abort(404)
    fotos = query("SELECT * FROM vehiculo_fotos WHERE vehiculo_id = ? ORDER BY orden, id", (vehiculo_id,))

    # El teléfono sale primero de lo que Daniel cargó en Admin (Datos de la
    # agencia) -- si todavía no cargó nada ahí, se usa el default confirmado
    # el 16/09/2026 (341 301-7371), pisable con la variable de entorno
    # WHATSAPP_COMERCIAL si hiciera falta.
    # Multi-tenant (18/09/2026): la ficha muestra los datos/WhatsApp de la
    # agencia dueña del vehículo (no siempre la de Daniel) -- si esa
    # agencia todavía no cargó nada en Admin, cae al default fijo de
    # siempre (pisable con WHATSAPP_COMERCIAL).
    agencia = obtener_config_agencia(vehiculo["agencia_id"] or 1)
    whatsapp_numero = (
        agencia.get("telefono")
        or os.environ.get("WHATSAPP_COMERCIAL", "5493413017371").strip()
    )
    whatsapp_link = None
    if whatsapp_numero:
        titulo_vehiculo = " ".join(
            str(p) for p in [vehiculo["marca"], vehiculo["modelo"], vehiculo["version"]] if p
        )
        mensaje = f"Hola! Te escribo por el {titulo_vehiculo} ({vehiculo['anio'] or 's/d'}) que vi publicado."
        whatsapp_link = f"https://wa.me/{whatsapp_numero}?text={quote_plus(mensaje)}"

    return render_template(
        "stock/ficha.html",
        vehiculo=vehiculo,
        fotos=fotos,
        foto_principal_url=foto_principal(vehiculo_id),
        whatsapp_link=whatsapp_link,
        estado_label=ESTADO_LABEL,
        equipamiento=equipamiento_destacado(vehiculo["equipamiento"]),
        agencia=agencia,
    )
