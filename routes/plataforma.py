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
    agencias_rows = query(
        """SELECT a.id, a.nombre_agencia, a.email, a.telefono AS telefono_registro,
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

    filas = todas
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
        q=q, orden=orden, direccion=direccion, orden_opciones=ORDEN_OPCIONES,
    )


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
