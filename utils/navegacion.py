"""Botones de navegación comunes a toda la app (pedido de Daniel 30/09/2026):
"‹ Volver" en las pantallas que no son del menú y "‹ Anterior / Siguiente ›"
en las fichas que se abren desde un listado. Instalada como app no hay botón
"atrás" del navegador, así que cada pantalla tiene que traer el suyo.

Se inyecta en todos los templates (ver `_inject_navegacion` en app.py) y lo
dibuja `templates/partials/barra_navegacion.html` arriba del título. Las
pantallas que ya tenían su propio "Volver" (Stock, Financiación, Tomas >
Fotos/Tasación, etc.) no figuran en VOLVER, así no aparece dos veces.
"""

from flask import request, session, url_for

from database import query


def _seguro(destino):
    """Solo rutas internas ("/algo"), igual que `_volver_seguro` en stock.py."""
    if destino and destino.startswith("/") and not destino.startswith("//") and "\\" not in destino:
        return destino
    return None


def _inicio():
    if session.get("agencia_id"):
        return url_for("dashboard.index")
    if session.get("superadmin_id"):
        return url_for("plataforma.agencias")
    return None


# Endpoint -> a dónde vuelve (a = request.view_args).
VOLVER = {
    "stock.nuevo": lambda a: url_for("stock.index"),
    "stock.editar": lambda a: url_for("stock.detalle", vehiculo_id=a["vehiculo_id"]),
    "pedidos.nuevo": lambda a: url_for("pedidos.index"),
    "pedidos.detalle": lambda a: url_for("pedidos.index", estado=request.args.get("estado") or None),
    "tomas.nueva": lambda a: url_for("tomas.index"),
    "tomas.detalle": lambda a: url_for("tomas.index", vista=request.args.get("vista") or None),
    "red.nueva": lambda a: url_for("red.index"),
    "cuenta.index": lambda a: _inicio(),
}


def volver_auto():
    ep = request.endpoint
    if ep not in VOLVER:
        return None
    return _seguro(request.args.get("volver")) or VOLVER[ep](request.view_args or {})


def nav_lista(ids, actual, enlace):
    """Posición dentro de un listado y links al anterior / siguiente."""
    if actual not in ids or len(ids) < 2:
        return None
    i = ids.index(actual)
    return {
        "pos": i + 1,
        "total": len(ids),
        "anterior": enlace(ids[i - 1]) if i > 0 else None,
        "siguiente": enlace(ids[i + 1]) if i < len(ids) - 1 else None,
    }


def _nav_pedidos(a):
    estado = request.args.get("estado")
    if not estado:  # se abrió desde otro lado (Matches, Stock...): sin listado
        return None
    ag = session["agencia_id"]
    if estado == "todos":
        filas = query("SELECT id FROM pedidos_clientes WHERE agencia_id = ? ORDER BY created_at DESC", (ag,))
    else:
        filas = query("SELECT id FROM pedidos_clientes WHERE agencia_id = ? AND estado = ? ORDER BY created_at DESC",
                      (ag, estado))
    return nav_lista([r["id"] for r in filas], a["pedido_id"],
                     lambda i: url_for("pedidos.detalle", pedido_id=i, estado=estado))


def _nav_tomas(a):
    vista = request.args.get("vista")
    if vista not in ("pendientes", "en_stock"):
        return None
    ag = session["agencia_id"]
    en_stock = {r["id"] for r in query(
        """SELECT t.id FROM tomas_vehiculo t JOIN vehiculos v ON v.id = t.vehiculo_id AND v.agencia_id = t.agencia_id
           WHERE t.agencia_id = ?""", (ag,))}
    ids = [r["id"] for r in query("SELECT id FROM tomas_vehiculo WHERE agencia_id = ? ORDER BY created_at DESC", (ag,))
           if (r["id"] in en_stock) == (vista == "en_stock")]
    return nav_lista(ids, a["toma_id"], lambda i: url_for("tomas.detalle", toma_id=i, vista=vista))


def _nav_financiacion(a):
    from utils.permisos import es_vendedor
    filas = query(
        "SELECT id, estado, creado_por_id FROM financiaciones WHERE estado != 'cancelado_reserva' "
        "AND COALESCE(agencia_id, 1) = ? ORDER BY created_at DESC", (session["agencia_id"],))
    if es_vendedor():  # mismo filtro que el listado de Financiación
        filas = [f for f in filas if f["estado"] == "pendiente_firma" or f["creado_por_id"] == session.get("usuario_id")]
    return nav_lista([f["id"] for f in filas], a["financiacion_id"],
                     lambda i: url_for("financiacion.detalle", financiacion_id=i))


NAV = {
    "pedidos.detalle": _nav_pedidos,
    "tomas.detalle": _nav_tomas,
    "financiacion.detalle": _nav_financiacion,
}


def nav_detalle():
    fn = NAV.get(request.endpoint)
    if not fn or not session.get("agencia_id"):
        return None
    return fn(request.view_args or {})
