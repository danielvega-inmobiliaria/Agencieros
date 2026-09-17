import os
import uuid
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from urllib.parse import quote_plus

from database import query, execute, foto_principal, obtener_catalogo
from sync_stock import sync_stock
from buscador import parsear_filtros, buscar_combinado
from ocr_titulo import extraer_datos_titulo, TesseractNoDisponible
from equipamiento_destacado import equipamiento_destacado

bp = Blueprint("stock", __name__, url_prefix="/stock")

ESTADOS = ["disponible", "por_ingresar", "en_reparacion", "vendido"]
ESTADO_LABEL = {
    "disponible": "Disponible",
    "por_ingresar": "Por ingresar",
    "en_reparacion": "En reparación",
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
    resultado = sync_stock()
    if resultado["error"]:
        flash(f"No se pudo sincronizar con STOCK: {resultado['error']}", "error")
    else:
        partes = []
        if resultado["nuevos"]:
            partes.append(f"{len(resultado['nuevos'])} vehículo(s) nuevo(s)")
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
    if filtros:
        resultados = buscar_combinado(filtros)
        vehiculos = None
    else:
        resultados = None
        if estado_filtro in ESTADOS:
            vehiculos = query("SELECT * FROM vehiculos WHERE estado = ? ORDER BY created_at DESC", (estado_filtro,))
        else:
            # "Todos" no incluye Vendido — solo se ve entrando puntualmente a
            # esa pestaña (pedido de Daniel 15/09/2026, continuación 19). El
            # buscador combinado (buscar_combinado, arriba) ya lo excluía.
            vehiculos = query("SELECT * FROM vehiculos WHERE estado != 'vendido' ORDER BY created_at DESC")

    conteos = {r["estado"]: r["c"] for r in query("SELECT estado, COUNT(*) c FROM vehiculos GROUP BY estado")}
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
    }
    if request.method == "POST":
        f = request.form
        propiedad = f.get("propiedad", "propio")
        es_consignacion = propiedad == "consignacion"
        vehiculo_id = execute(
            """INSERT INTO vehiculos
               (marca, modelo, version, anio, km, combustible, caja, color, dominio, estado,
                equipamiento, observaciones, documentacion, valor_compra, gastos, valor_publicado,
                fecha_ingreso, entrega_quien, fecha_ingreso_estimada,
                propiedad, consignante_nombre, consignante_telefono)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
            ),
        )

        # Módulo 3: aviso automático si hay un pedido de cliente que matchea.
        matches = query(
            """SELECT * FROM pedidos_clientes
               WHERE estado = 'buscando' AND marca = ? AND modelo = ?
                 AND (anio_desde IS NULL OR ? >= anio_desde)
                 AND (anio_hasta IS NULL OR ? <= anio_hasta)""",
            (f.get("marca"), f.get("modelo"), f.get("anio") or 0, f.get("anio") or 9999),
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

        return redirect(url_for("stock.detalle", vehiculo_id=vehiculo_id))

    return render_template("stock/form.html", vehiculo=None, prefill=prefill, estados=ESTADOS, estado_label=ESTADO_LABEL)


@bp.route("/<int:vehiculo_id>")
def detalle(vehiculo_id):
    vehiculo = query("SELECT * FROM vehiculos WHERE id = ?", (vehiculo_id,), one=True)
    if not vehiculo:
        flash("Vehículo no encontrado.", "error")
        return redirect(url_for("stock.index"))
    fotos = query("SELECT * FROM vehiculo_fotos WHERE vehiculo_id = ? ORDER BY orden, id", (vehiculo_id,))
    return render_template(
        "stock/detalle.html", vehiculo=vehiculo, rent=_rentabilidad(vehiculo), estado_label=ESTADO_LABEL, fotos=fotos
    )


@bp.route("/<int:vehiculo_id>/fotos", methods=["POST"])
def subir_fotos(vehiculo_id):
    vehiculo = query("SELECT * FROM vehiculos WHERE id = ?", (vehiculo_id,), one=True)
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
    carpeta = os.path.join(current_app.root_path, "static", "uploads", "vehiculos", str(vehiculo_id))
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
    foto = query(
        "SELECT * FROM vehiculo_fotos WHERE id = ? AND vehiculo_id = ?", (foto_id, vehiculo_id), one=True
    )
    if foto:
        execute("DELETE FROM vehiculo_fotos WHERE id = ?", (foto_id,))
        ruta_local = os.path.join(current_app.root_path, foto["url"].lstrip("/"))
        try:
            if os.path.isfile(ruta_local):
                os.remove(ruta_local)
        except OSError:
            pass
        flash("Foto eliminada.", "success")
    return redirect(url_for("stock.detalle", vehiculo_id=vehiculo_id))


@bp.route("/<int:vehiculo_id>/editar", methods=["GET", "POST"])
def editar(vehiculo_id):
    vehiculo = query("SELECT * FROM vehiculos WHERE id = ?", (vehiculo_id,), one=True)
    if not vehiculo:
        flash("Vehículo no encontrado.", "error")
        return redirect(url_for("stock.index"))

    if request.method == "POST":
        f = request.form
        fecha_venta = str(date.today()) if f.get("estado") == "vendido" and vehiculo["estado"] != "vendido" else vehiculo["fecha_venta"]
        propiedad = f.get("propiedad", "propio")
        es_consignacion = propiedad == "consignacion"
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

    # Default confirmado por Daniel el 16/09/2026 (341 301-7371). Se puede
    # sobreescribir con la variable de entorno WHATSAPP_COMERCIAL si en el
    # futuro cambia el número o hay más de una agencia.
    whatsapp_numero = os.environ.get("WHATSAPP_COMERCIAL", "5493413017371").strip()
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
    )
