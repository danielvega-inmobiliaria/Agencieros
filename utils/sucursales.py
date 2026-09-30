"""Sucursales por agencia (29/09/2026, paso 3 de "reorganizar cuentas y Red").

- Una agencia puede tener 0, 1 o varias sucursales. Con 0 o 1 la app se ve
  igual que siempre (no hay nada que filtrar).
- Con 2 o más, Stock y Dashboard muestran un selector de sucursal. La
  elección queda en la sesión (vale para las dos pantallas) y arranca en la
  sucursal del usuario si tiene una asignada; el dueño sin sucursal arranca
  en "Todas" (vista consolidada).
- El vendedor ve el stock de todas las sucursales (puede vender cualquier
  unidad, decidido por Daniel 29/09/2026), pero arranca filtrado en la suya
  y lo que carga queda en su sucursal.
- ventas y financiaciones toman la sucursal del vehículo automáticamente
  (triggers en database._migrar_sucursales).
"""
from flask import request, session

from database import query

TODAS = "todas"


def sucursales_de(agencia_id, incluir_inactivas=False):
    if not agencia_id:
        return []
    sql = "SELECT * FROM sucursales WHERE agencia_id = ?"
    if not incluir_inactivas:
        sql += " AND activa = 1"
    return query(sql + " ORDER BY id", (agencia_id,))


def sucursal_del_usuario():
    uid = session.get("usuario_id")
    if not uid:
        return None
    fila = query(
        """SELECT u.sucursal_id FROM agencia_usuarios u
           JOIN sucursales s ON s.id = u.sucursal_id AND s.activa = 1
           WHERE u.id = ? AND u.agencia_id = ?""",
        (uid, session.get("agencia_id")), one=True,
    )
    return fila["sucursal_id"] if fila else None


def sucursal_para_alta():
    """Sucursal con la que nace una unidad nueva: la del usuario; si no tiene,
    la elegida en el selector; si no, la primera de la agencia (o None)."""
    elegida = sucursal_del_usuario() or sucursal_seleccionada()
    if elegida:
        return elegida
    sucs = sucursales_de(session.get("agencia_id"))
    return sucs[0]["id"] if sucs else None


def sucursal_seleccionada():
    """Sucursal elegida para filtrar (int) o None = todas / sin filtro.
    Lee ?suc= (id o 'todas') y lo recuerda en la sesión."""
    agencia_id = session.get("agencia_id")
    sucs = sucursales_de(agencia_id)
    if len(sucs) < 2:
        return None
    ids = {s["id"] for s in sucs}
    pedido = request.args.get("suc")
    if pedido is not None:
        if pedido == TODAS:
            session["suc_sel"] = TODAS
        elif pedido.isdigit() and int(pedido) in ids:
            session["suc_sel"] = int(pedido)
    elegido = session.get("suc_sel")
    if elegido == TODAS:
        return None
    if isinstance(elegido, int) and elegido in ids:
        return elegido
    return sucursal_del_usuario()


def filtro_sql(columna="sucursal_id"):
    """(" AND columna = ?", [id]) o ("", []) si no hay filtro."""
    s = sucursal_seleccionada()
    if s is None:
        return "", []
    return f" AND {columna} = ?", [s]


def contexto_selector():
    """Datos para partials/selector_sucursal.html."""
    sucs = sucursales_de(session.get("agencia_id"))
    if len(sucs) < 2:
        return {"sucursales_sel": [], "sucursal_sel": None, "sucursal_sel_nombre": None}
    sel = sucursal_seleccionada()
    nombre = next((s["nombre"] for s in sucs if s["id"] == sel), None)
    return {"sucursales_sel": sucs, "sucursal_sel": sel, "sucursal_sel_nombre": nombre}


def nombres_sucursales(agencia_id):
    return {s["id"]: s["nombre"] for s in sucursales_de(agencia_id, incluir_inactivas=True)}
