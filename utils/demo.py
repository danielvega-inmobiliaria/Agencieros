"""Aislamiento de la agencia DEMO (06/10/2026, ver demo_agencia.py).

La Red de Agencieros es compartida entre agencias reales; la demo tiene la
suya: la demo (y las agencias ficticias es_demo=2) solo ven publicaciones de
agencias es_demo > 0, y las agencias reales nunca ven las de la demo.
"""
from flask import session


def _es_demo(agencia_id):
    if not agencia_id:
        return False
    from database import query
    fila = query("SELECT es_demo FROM agencias WHERE id = ?", (agencia_id,), one=True)
    return bool(fila and fila["es_demo"])


def condicion_red(alias="", agencia_id=None):
    """Fragmento SQL (sin parámetros) para filtrar red_publicaciones según
    quién mira. `alias` = prefijo de tabla, ej. "red_publicaciones."."""
    if agencia_id is None:
        agencia_id = session.get("agencia_id")
    col = f"{alias}agencia_id"
    if _es_demo(agencia_id):
        return f"{col} IN (SELECT id FROM agencias WHERE es_demo > 0)"
    return f"COALESCE({col}, 0) NOT IN (SELECT id FROM agencias WHERE es_demo > 0)"
