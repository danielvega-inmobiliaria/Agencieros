"""Panel de Agencias (18/09/2026, ampliado el mismo día con búsqueda +
orden, "última actividad", y una ficha de detalle por agencia).

Vista de plataforma para el admin de AGENCIEROS (plataforma_admins, desde 28/09/2026) --
no es un módulo de negocio de ninguna agencia en particular, sino el
"pulso" del sector: quiénes son las agencias registradas, dónde están, y
cuánto están usando la app (stock, ventas, financiación, y último
request autenticado). Pensado para cuando empiecen a sumarse agencias
reales a la Red -- hoy con pocas agencias sirve igual para dejar el panel
armado y probado de antemano.

El listado (agencias()) muestra lo justo para escanear rápido de un
vistazo (pedido de Daniel: compacto, poco texto). Los datos de contacto
(teléfono, contacto de referencia) viven en la ficha de detalle
(detalle()), a un click de cada fila.

Acceso: gateado en app.py (SOLO_SUPERADMIN) -- solo el admin de la
plataforma; ninguna agencia (tampoco Italia Automotores) entra acá.
"""

from datetime import datetime, timedelta

from flask import Blueprint, abort, render_template, request, redirect, url_for, flash

from database import query, execute

bp = Blueprint("plataforma", __name__, url_prefix="/plataforma")

# Campos por los que se puede ordenar el listado, y la función que saca la
# clave de orden de cada fila ya armada (ver _armar_filas). "actividad",
# "stock", "ventas" y "creditos" son justamente los pedidos por Daniel
# (mayor stock / mayores ventas / mayores créditos) + última actividad.
_CLAVES_ORDEN = {
    "nombre":    lambda f: (f["nombre"] or "").lower(),
    "actividad": lambda f: f["ultima_actividad"] or "",
    "stock":     lambda f: f["stock_total"],
    "ventas":    lambda f: f["ventas_totales"],
    "creditos":  lambda f: f["creditos_monto"],
    "consultas": lambda f: (f["consultas_mes"], f["consultas_total"]),
}
ORDEN_OPCIONES = [
    ("nombre", "Nombre"),
    ("actividad", "Última actividad"),
    ("stock", "Stock total"),
    ("ventas", "Ventas totales"),
    ("creditos", "Créditos (monto)"),
    ("consultas", "Consultas de precios"),
]


def _formatear_fecha(iso_str):
    """'YYYY-MM-DD HH:MM:SS' (SQLite) -> 'DD/MM/YYYY HH:MM' para la UI."""
    if not iso_str:
        return None
    try:
        # SQLite guarda en UTC: se muestra en hora de Argentina (UTC-3, sin horario de verano).
        return (datetime.strptime(iso_str, "%Y-%m-%d %H:%M:%S") - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso_str


def _armar_filas():
    """Une agencias + agencia_config + agregados de stock/ventas/créditos
    en una lista de dicts lista para filtrar/ordenar/mostrar (listado) o
    buscar por id (detalle) -- una sola fuente de verdad para no
    duplicar la lógica de agregación en dos lugares."""
    from utils.antibot import asegurar_columna_conservar
    asegurar_columna_conservar()
    agencias_rows = query(
        """SELECT a.id, a.conservar, a.nombre_agencia, a.email, a.telefono AS telefono_registro,
                  a.contacto_referencia, a.email_verificado, a.activo, a.plan,
                  a.created_at, a.ultima_actividad, a.origen, a.demo_ultimo_ingreso,
                  c.telefono AS telefono_comercial, c.direccion, c.ciudad, c.provincia
           FROM agencias a
           LEFT JOIN agencia_config c ON c.agencia_id = a.id
           WHERE COALESCE(a.es_demo, 0) = 0"""
    )

    stock_rows = query(
        """SELECT agencia_id,
                  SUM(CASE WHEN estado = 'disponible' THEN 1 ELSE 0 END) AS disponibles,
                  SUM(CASE WHEN estado = 'por_ingresar' THEN 1 ELSE 0 END) AS por_ingresar,
                  SUM(CASE WHEN estado = 'en_reparacion' THEN 1 ELSE 0 END) AS en_reparacion,
                  SUM(CASE WHEN estado = 'vendido' THEN 1 ELSE 0 END) AS ventas_totales,
                  SUM(CASE WHEN estado = 'vendido'
                           AND strftime('%Y-%m', fecha_venta) = strftime('%Y-%m', 'now')
                      THEN 1 ELSE 0 END) AS ventas_mes
           FROM vehiculos
           GROUP BY agencia_id"""
    )
    stock_por_agencia = {r["agencia_id"]: r for r in stock_rows}

    credito_rows = query(
        """SELECT agencia_id, COUNT(*) AS cantidad, COALESCE(SUM(monto_financiado), 0) AS monto_total
           FROM financiaciones
           GROUP BY agencia_id"""
    )
    credito_por_agencia = {r["agencia_id"]: r for r in credito_rows}

    # Consultas de precios (28/09/2026): para medir si cada agencia usa la consulta.
    consulta_rows = query(
        """SELECT agencia_id,
                  COUNT(*) AS total,
                  SUM(CASE WHEN created_at >= datetime('now', '-7 days') THEN 1 ELSE 0 END) AS semana,
                  SUM(CASE WHEN strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now') THEN 1 ELSE 0 END) AS mes,
                  MAX(created_at) AS ultima
           FROM consultas_precios
           GROUP BY agencia_id"""
    )
    consulta_por_agencia = {r["agencia_id"]: r for r in consulta_rows}

    filas = []
    for a in agencias_rows:
        s = stock_por_agencia.get(a["id"])
        c = credito_por_agencia.get(a["id"])
        cp = consulta_por_agencia.get(a["id"])
        disponibles = (s["disponibles"] if s else 0) or 0
        por_ingresar = (s["por_ingresar"] if s else 0) or 0
        en_reparacion = (s["en_reparacion"] if s else 0) or 0
        filas.append({
            "id": a["id"],
            "nombre": a["nombre_agencia"],
            "plan": a["plan"] or "libre",
            "email": a["email"],
            "telefono": a["telefono_comercial"] or a["telefono_registro"],
            "contacto_referencia": a["contacto_referencia"],
            "direccion": a["direccion"],
            "ciudad": a["ciudad"],
            "provincia": a["provincia"],
            "por_invitacion": a["origen"] == "invitacion",
            "demo_ultimo_ingreso_fmt": _formatear_fecha(a["demo_ultimo_ingreso"]),
            "verificada": bool(a["email_verificado"]),
            "conservar": bool(a["conservar"]),
            "activa": bool(a["activo"]),
            "alta": a["created_at"],
            "alta_fmt": _formatear_fecha(a["created_at"]),
            "ultima_actividad": a["ultima_actividad"],
            "ultima_actividad_fmt": _formatear_fecha(a["ultima_actividad"]),
            "disponibles": disponibles,
            "por_ingresar": por_ingresar,
            "en_reparacion": en_reparacion,
            "stock_total": disponibles + por_ingresar + en_reparacion,
            "ventas_mes": (s["ventas_mes"] if s else 0) or 0,
            "ventas_totales": (s["ventas_totales"] if s else 0) or 0,
            "creditos_cantidad": (c["cantidad"] if c else 0) or 0,
            "creditos_monto": (c["monto_total"] if c else 0) or 0,
            "consultas_semana": (cp["semana"] if cp else 0) or 0,
            "consultas_mes": (cp["mes"] if cp else 0) or 0,
            "consultas_total": (cp["total"] if cp else 0) or 0,
            "ultima_consulta_fmt": _formatear_fecha(cp["ultima"]) if cp else None,
        })
    return filas


@bp.route("/agencias")
def agencias():
    q = (request.args.get("q") or "").strip().lower()
    orden = request.args.get("orden", "nombre")
    if orden not in _CLAVES_ORDEN:
        orden = "nombre"
    direccion = request.args.get("dir", "asc")
    if direccion not in ("asc", "desc"):
        direccion = "asc"

    todas = _armar_filas()

    # El resumen ("pulso" general) siempre es sobre TODAS las agencias, no
    # sobre lo que quede después de buscar -- si no, buscar "Roldán" haría
    # que las tarjetas de arriba parezcan que la plataforma achicó.
    resumen = {
        "total_agencias": len(todas),
        "verificadas": sum(1 for f in todas if f["verificada"]),
        "ventas_mes_total": sum(f["ventas_mes"] for f in todas),
        "creditos_monto_total": sum(f["creditos_monto"] for f in todas),
        "consultas_mes_total": sum(f["consultas_mes"] for f in todas),
        "consultas_semana_total": sum(f["consultas_semana"] for f in todas),
        "mensajes_sin_responder": query("SELECT COUNT(*) AS c FROM mensajes_admin WHERE respondida = 0", one=True)["c"],
    }

    ver_todas = request.args.get("sin_validar") == "1"
    resumen["sin_validar"] = sum(1 for f in todas if not f["verificada"] and not f["conservar"])
    # Por defecto solo las que validaron el mail (el listado con miles de
    # registros de bots era inmanejable); ?sin_validar=1 las muestra todas.
    filas = todas if ver_todas else [f for f in todas if f["verificada"] or f["conservar"]]
    if q:
        def _matchea(f):
            campos = [f["nombre"], f["email"], f["ciudad"], f["provincia"]]
            return any(q in (c or "").lower() for c in campos)
        filas = [f for f in filas if _matchea(f)]

    filas.sort(key=_CLAVES_ORDEN[orden], reverse=(direccion == "desc"))

    return render_template(
        "plataforma/agencias.html",
        filas=filas, resumen=resumen,
        demo_codigo=(query("SELECT demo_codigo FROM agencias WHERE es_demo = 1 ORDER BY id LIMIT 1", one=True) or {"demo_codigo": None})["demo_codigo"],
        q=q, orden=orden, direccion=direccion, orden_opciones=ORDEN_OPCIONES, ver_todas=ver_todas,
    )


@bp.route("/agencias/<int:agencia_id>/conservar", methods=["POST"])
def conservar(agencia_id):
    """Marca/desmarca una cuenta sin validar para que la limpieza no la borre."""
    from utils.antibot import asegurar_columna_conservar
    asegurar_columna_conservar()
    fila = query("SELECT conservar FROM agencias WHERE id = ?", (agencia_id,), one=True)
    if fila is None:
        abort(404)
    nuevo = 0 if fila["conservar"] else 1
    execute("UPDATE agencias SET conservar = ? WHERE id = ?", (nuevo, agencia_id))
    flash("Listo: esta cuenta no se borra al limpiar." if nuevo else "Esta cuenta vuelve a poder borrarse al limpiar.", "success")
    return redirect(url_for("plataforma.detalle", agencia_id=agencia_id))


@bp.route("/agencias/limpiar-sin-validar", methods=["POST"])
def limpiar_sin_validar():
    """Borra las cuentas que nunca validaron el mail (bots/abandonadas) con
    más de 24 horas (09/11/2026)."""
    from utils.antibot import purgar_sin_validar
    # El código de mail vence a los 15 min: una cuenta sin validar de más de
    # 1 hora ya no la está validando nadie. Tandas de 3000 por clic.
    n = purgar_sin_validar(horas=1, limite=3000)
    flash(f"Se borraron {n} agencias que nunca validaron su mail."
          + (" Quedan más: tocá el botón de nuevo." if n >= 3000 else ""), "success")
    return redirect(url_for("plataforma.agencias"))


@bp.route("/demo/reiniciar", methods=["POST"])
def reiniciar_demo_ruta():
    """Vuelve la agencia demo a su estado original (06/10/2026)."""
    from demo_agencia import reiniciar_demo
    reiniciar_demo()
    flash("Agencia demo reiniciada: vuelve a tener los datos de ejemplo.", "success")
    return redirect(url_for("plataforma.agencias"))


@bp.route("/agencias/<int:agencia_id>")
def detalle(agencia_id):
    fila = next((f for f in _armar_filas() if f["id"] == agencia_id), None)
    if fila is None:
        abort(404)
    usuarios = query(
        """SELECT nombre, email, rol, activo, ultimo_ingreso FROM agencia_usuarios
           WHERE agencia_id = ? ORDER BY CASE rol WHEN 'dueno' THEN 0 ELSE 1 END, nombre""",
        (agencia_id,),
    )
    from utils.planes import PLANES, resumen
    return render_template("plataforma/detalle.html", f=fila, usuarios=usuarios,
                           planes=PLANES, plan=resumen(agencia_id))


@bp.route("/agencias/<int:agencia_id>/plan", methods=["POST"])
def cambiar_plan(agencia_id):
    """Cambiar el plan de una agencia (30/09/2026, paso 5). Sin cobro
    automático: el admin lo asigna a mano."""
    from utils.planes import PLANES
    plan = request.form.get("plan")
    if plan not in PLANES or not query("SELECT 1 FROM agencias WHERE id = ?", (agencia_id,), one=True):
        abort(404)
    execute("UPDATE agencias SET plan = ? WHERE id = ?", (plan, agencia_id))
    flash(f"Plan cambiado a {PLANES[plan]['nombre']}.", "success")
    return redirect(url_for("plataforma.detalle", agencia_id=agencia_id))


@bp.route("/mensajes")
def mensajes():
    """Bandeja de consultas de las agencias, agrupadas en una conversación por
    agencia (28/09/2026). Arriba las que esperan respuesta (la última palabra
    es de la agencia), ordenadas por el último mensaje; abajo, plegadas, las
    ya respondidas. Si una agencia vuelve a escribir, su conversación sube
    sola a "Por responder". Al abrir la bandeja todo queda leído."""
    from routes.mensajes import TIPO_LABEL
    filas = query(
        """SELECT m.*, a.nombre_agencia, a.email, a.telefono
           FROM mensajes_admin m LEFT JOIN agencias a ON a.id = m.agencia_id
           ORDER BY m.created_at, m.id"""
    )
    convs = {}
    for m in filas:
        c = convs.setdefault(m["agencia_id"], {
            "agencia_id": m["agencia_id"], "nombre": m["nombre_agencia"] or "Agencia borrada",
            "email": m["email"], "telefono": m["telefono"], "mensajes": [], "nuevos": 0,
        })
        d = dict(m)
        d["fecha_fmt"] = _formatear_fecha(m["created_at"])
        d["tipo_label"] = TIPO_LABEL.get(m["tipo"], m["tipo"])
        c["mensajes"].append(d)
        if (m["autor"] or "agencia") == "agencia" and not m["leido"]:
            c["nuevos"] += 1
    for c in convs.values():
        ultimo = c["mensajes"][-1]
        c["ultimo"] = ultimo["created_at"]
        c["ultimo_fmt"] = ultimo["fecha_fmt"]
        c["pendiente"] = (ultimo["autor"] or "agencia") == "agencia" and not ultimo["respondida"]
    pendientes = sorted([c for c in convs.values() if c["pendiente"]], key=lambda c: c["ultimo"], reverse=True)
    respondidas = sorted([c for c in convs.values() if not c["pendiente"]], key=lambda c: c["ultimo"], reverse=True)
    execute("UPDATE mensajes_admin SET leido = 1 WHERE leido = 0")
    return render_template("plataforma/mensajes.html", pendientes=pendientes, respondidas=respondidas)


@bp.route("/mensajes/<int:agencia_id>/responder", methods=["POST"])
def responder_mensaje(agencia_id):
    """Respuesta del admin dentro de la app: queda en la conversación, cierra
    lo pendiente de esa agencia y le avisa por mail."""
    from utils.notificaciones import avisar_agencia
    texto = (request.form.get("respuesta") or "").strip()[:2000]
    agencia = query("SELECT nombre_agencia, email FROM agencias WHERE id = ?", (agencia_id,), one=True)
    if agencia is None:
        abort(404)
    if texto:
        execute(
            """INSERT INTO mensajes_admin (agencia_id, tipo, mensaje, autor, leido, respondida, leido_agencia)
               VALUES (?, 'respuesta', ?, 'admin', 1, 1, 0)""",
            (agencia_id, texto),
        )
        avisar_agencia(
            agencia["email"],
            "Respuesta de AGENCIEROS a tu consulta",
            f"Hola {agencia['nombre_agencia']},\n\n{texto}\n\nPodés seguir la conversación desde \"Consultas y avisos\".",
            ruta="/mensajes/",
        )
    execute("UPDATE mensajes_admin SET respondida = 1, leido = 1 WHERE agencia_id = ? AND respondida = 0", (agencia_id,))
    return redirect(url_for("plataforma.mensajes"))


@bp.route("/demo/codigo", methods=["POST"])
def renovar_codigo_demo():
    """Genera un código nuevo para el link de la demo (08/10/2026). Corta el
    acceso a quien tenía el link anterior y a las sesiones demo abiertas."""
    import secrets
    from demo_agencia import reiniciar_demo
    reiniciar_demo()  # asegura que la agencia demo exista
    execute("UPDATE agencias SET demo_codigo = ? WHERE es_demo = 1", (secrets.token_urlsafe(6),))
    flash("Código de demo renovado: el link anterior dejó de funcionar y se cerraron las sesiones abiertas.", "success")
    return redirect(url_for("plataforma.agencias"))


# ---------------------------------------------------------------------
# Prospectos (10/11/2026): agencias a las que se les ofrece Agencieros.
# Se contactan DE A UNA, con mensaje personal por WhatsApp (nada de envíos
# masivos: riesgo de bloqueo del número). El botón abre WhatsApp con el
# mensaje base ya armado y marca al prospecto como «contactado».
# ---------------------------------------------------------------------
ESTADOS_PROSPECTO = [
    ("nuevo", "Nuevo"), ("contactado", "Contactado"), ("respondio", "Respondió"),
    ("interesado", "Interesado"), ("registrado", "Registrado"), ("descartado", "Descartado"),
]
_MENSAJE_BASE_DEFAULT = (
    "Hola {nombre}, soy Daniel, de Italia Automotores (Roldán). Armé una app para agencias de autos, "
    "Agencieros: consulta de precios con la revista del mes, stock, web propia para tu agencia y una red "
    "para compartir autos entre colegas. ¿Te cuento cómo funciona? app.agencieros.net.ar"
)
_POR_PAGINA = 50


def _mensaje_base():
    fila = query("SELECT valor FROM prospectos_config WHERE clave = 'mensaje'", one=True)
    return (fila["valor"] if fila and fila["valor"] else _MENSAJE_BASE_DEFAULT)


def _solo_digitos(x):
    return "".join(ch for ch in (x or "") if ch.isdigit())


def _primer_nombre(contacto, agencia):
    """Primer nombre de la persona de contacto; si no hay, vacío (el saludo queda «Hola»)."""
    base = (contacto or "").strip()
    if not base:
        return ""
    return base.split()[0].strip(" ,.-").capitalize()


def _armar_mensaje(plantilla, p):
    texto = plantilla.replace("{agencia}", (p["agencia"] or "").strip())
    nombre = _primer_nombre(p["contacto"], p["agencia"])
    texto = texto.replace("{nombre}", nombre)
    # «Hola ,» cuando no hay nombre -> «Hola,»
    return texto.replace(" ,", ",").replace("Hola  ", "Hola ").strip()


@bp.route("/prospectos")
def prospectos():
    from urllib.parse import quote
    estado = request.args.get("estado", "nuevo")
    grupo = (request.args.get("grupo") or "").strip()
    q = (request.args.get("q") or "").strip()
    solo_wa = request.args.get("wa", "1") == "1"
    p_raw = request.args.get("p", "1") or "1"
    pagina = max(1, int(p_raw)) if p_raw.isdigit() else 1

    cond, params = [], []
    if estado and estado != "todos":
        cond.append("estado = ?"); params.append(estado)
    if grupo:
        cond.append("grupo = ?"); params.append(grupo)
    if solo_wa:
        cond.append("COALESCE(whatsapp, '') != ''")
    if q:
        cond.append("(LOWER(COALESCE(agencia,'')) LIKE ? OR LOWER(COALESCE(contacto,'')) LIKE ? OR LOWER(COALESCE(ciudad,'')) LIKE ?)")
        params += [f"%{q.lower()}%"] * 3
    donde = (" WHERE " + " AND ".join(cond)) if cond else ""
    total = query(f"SELECT COUNT(*) AS c FROM prospectos{donde}", tuple(params), one=True)["c"]
    filas = query(f"SELECT * FROM prospectos{donde} ORDER BY id LIMIT ? OFFSET ?",
                  tuple(params) + (_POR_PAGINA, (pagina - 1) * _POR_PAGINA))
    plantilla = _mensaje_base()
    items = []
    for f in filas:
        num = _solo_digitos(f["whatsapp"])
        link = f"https://wa.me/{num}?text={quote(_armar_mensaje(plantilla, f))}" if len(num) >= 10 else None
        items.append({"p": f, "wa": link})
    conteo = {r["estado"]: r["c"] for r in query("SELECT estado, COUNT(*) AS c FROM prospectos GROUP BY estado")}
    grupos = [r["grupo"] for r in query("SELECT DISTINCT grupo FROM prospectos WHERE COALESCE(grupo,'') != '' ORDER BY grupo")]
    return render_template(
        "plataforma/prospectos.html", items=items, total=total, pagina=pagina,
        paginas=max(1, -(-total // _POR_PAGINA)), estado=estado, grupo=grupo, q=q, solo_wa=solo_wa,
        estados=ESTADOS_PROSPECTO, conteo=conteo, total_general=sum(conteo.values()), grupos=grupos,
        mensaje=plantilla,
    )


@bp.route("/prospectos/mensaje", methods=["POST"])
def prospectos_mensaje():
    texto = (request.form.get("mensaje") or "").strip()[:1000]
    if not texto:
        texto = _MENSAJE_BASE_DEFAULT
    execute("INSERT INTO prospectos_config (clave, valor) VALUES ('mensaje', ?) "
            "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor", (texto,))
    flash("Mensaje base guardado.", "success")
    return redirect(request.referrer or url_for("plataforma.prospectos"))


@bp.route("/prospectos/<int:pid>/estado", methods=["POST"])
def prospecto_estado(pid):
    nuevo = request.form.get("estado") or (request.get_json(silent=True) or {}).get("estado")
    if nuevo not in {e for e, _ in ESTADOS_PROSPECTO}:
        abort(400)
    if nuevo == "contactado":
        execute("UPDATE prospectos SET estado = ?, fecha_contacto = datetime('now', '-3 hours') WHERE id = ?", (nuevo, pid))
    else:
        execute("UPDATE prospectos SET estado = ? WHERE id = ?", (nuevo, pid))
    if request.is_json or request.headers.get("X-Requested-With") == "fetch":
        return {"ok": True}
    return redirect(request.referrer or url_for("plataforma.prospectos"))


@bp.route("/prospectos/<int:pid>/contactado", methods=["POST"])
def prospecto_contactado(pid):
    """Se llama al tocar «WhatsApp»: pasa de nuevo a contactado (no pisa estados más avanzados)."""
    execute("UPDATE prospectos SET estado = CASE WHEN estado = 'nuevo' THEN 'contactado' ELSE estado END, "
            "fecha_contacto = datetime('now', '-3 hours') WHERE id = ?", (pid,))
    return {"ok": True}


@bp.route("/prospectos/importar", methods=["POST"])
def prospectos_importar():
    """Importa un CSV (UTF-8) con columnas: agencia, contacto, whatsapp, ciudad,
    provincia, grupo, estado, fecha_contacto, notas, mail, instagram, link.
    No duplica: se saltea al que ya existe por WhatsApp (o por agencia + grupo)."""
    import csv, io
    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename:
        flash("Elegí el archivo CSV a importar.", "error")
        return redirect(url_for("plataforma.prospectos"))
    try:
        texto = archivo.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("El archivo tiene que estar guardado en UTF-8.", "error")
        return redirect(url_for("plataforma.prospectos"))
    lector = csv.DictReader(io.StringIO(texto))
    ya_wa = {_solo_digitos(r["whatsapp"]) for r in query("SELECT whatsapp FROM prospectos") if _solo_digitos(r["whatsapp"])}
    ya_ag = {((r["agencia"] or "").strip().lower(), (r["grupo"] or "").strip().lower()) for r in query("SELECT agencia, grupo FROM prospectos")}
    estados = {e for e, _ in ESTADOS_PROSPECTO}
    nuevos = saltados = 0
    for fila in lector:
        agencia = (fila.get("agencia") or "").strip()
        wa = _solo_digitos(fila.get("whatsapp"))
        clave = (agencia.lower(), (fila.get("grupo") or "").strip().lower())
        if not agencia and not wa:
            continue
        if (wa and wa in ya_wa) or (not wa and clave in ya_ag):
            saltados += 1
            continue
        est = (fila.get("estado") or "nuevo").strip().lower()
        execute(
            """INSERT INTO prospectos (agencia, contacto, whatsapp, ciudad, provincia, grupo, estado,
                                       fecha_contacto, notas, mail, instagram, link)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (agencia, (fila.get("contacto") or "").strip() or None, wa or None,
             (fila.get("ciudad") or "").strip() or None, (fila.get("provincia") or "").strip() or None,
             (fila.get("grupo") or "").strip() or None, est if est in estados else "nuevo",
             (fila.get("fecha_contacto") or "").strip() or None, (fila.get("notas") or "").strip() or None,
             (fila.get("mail") or "").strip() or None, (fila.get("instagram") or "").strip() or None,
             (fila.get("link") or "").strip() or None))
        if wa:
            ya_wa.add(wa)
        ya_ag.add(clave)
        nuevos += 1
    flash(f"Importados {nuevos} prospectos ({saltados} ya estaban).", "success")
    return redirect(url_for("plataforma.prospectos"))
