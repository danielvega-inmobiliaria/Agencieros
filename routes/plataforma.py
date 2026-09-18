"""Panel de Agencias (18/09/2026, ampliado el mismo día con búsqueda +
orden, "última actividad", y una ficha de detalle por agencia).

Vista de plataforma para Daniel (agencia_id=1, el dueño de AGENCIEROS) --
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

Acceso: gateado en app.py (MODULOS_SOLO_AGENCIA_1) -- solo la agencia 1
puede ver esto, igual que Dashboard/Finanzas/Tomas/Financiación.
"""

from datetime import datetime

from flask import Blueprint, abort, render_template, request

from database import query

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
}
ORDEN_OPCIONES = [
    ("nombre", "Nombre"),
    ("actividad", "Última actividad"),
    ("stock", "Stock total"),
    ("ventas", "Ventas totales"),
    ("creditos", "Créditos (monto)"),
]


def _formatear_fecha(iso_str):
    """'YYYY-MM-DD HH:MM:SS' (SQLite) -> 'DD/MM/YYYY HH:MM' para la UI."""
    if not iso_str:
        return None
    try:
        return datetime.strptime(iso_str, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso_str


def _armar_filas():
    """Une agencias + agencia_config + agregados de stock/ventas/créditos
    en una lista de dicts lista para filtrar/ordenar/mostrar (listado) o
    buscar por id (detalle) -- una sola fuente de verdad para no
    duplicar la lógica de agregación en dos lugares."""
    agencias_rows = query(
        """SELECT a.id, a.nombre_agencia, a.email, a.telefono AS telefono_registro,
                  a.contacto_referencia, a.email_verificado, a.activo,
                  a.created_at, a.ultima_actividad,
                  c.telefono AS telefono_comercial, c.direccion, c.ciudad, c.provincia
           FROM agencias a
           LEFT JOIN agencia_config c ON c.agencia_id = a.id"""
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

    filas = []
    for a in agencias_rows:
        s = stock_por_agencia.get(a["id"])
        c = credito_por_agencia.get(a["id"])
        disponibles = (s["disponibles"] if s else 0) or 0
        por_ingresar = (s["por_ingresar"] if s else 0) or 0
        en_reparacion = (s["en_reparacion"] if s else 0) or 0
        filas.append({
            "id": a["id"],
            "nombre": a["nombre_agencia"],
            "email": a["email"],
            "telefono": a["telefono_comercial"] or a["telefono_registro"],
            "contacto_referencia": a["contacto_referencia"],
            "direccion": a["direccion"],
            "ciudad": a["ciudad"],
            "provincia": a["provincia"],
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
        q=q, orden=orden, direccion=direccion, orden_opciones=ORDEN_OPCIONES,
    )


@bp.route("/agencias/<int:agencia_id>")
def detalle(agencia_id):
    fila = next((f for f in _armar_filas() if f["id"] == agencia_id), None)
    if fila is None:
        abort(404)
    return render_template("plataforma/detalle.html", f=fila)
