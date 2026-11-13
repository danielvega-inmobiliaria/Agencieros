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
        base = f"{col} IN (SELECT id FROM agencias WHERE es_demo > 0)"
    else:
        base = f"COALESCE({col}, 0) NOT IN (SELECT id FROM agencias WHERE es_demo > 0)"
    return base + _condicion_visibilidad(agencia_id)


def _condicion_visibilidad(agencia_id):
    """Sub Red: quién ve cada publicación. Lo propio siempre se ve; lo de
    otra agencia solo si no te bloqueó ("No compartir con") y es para toda
    la red o te eligió entre «Solo estas agencias». Sin agencia (admin de la
    plataforma) no se filtra. Se usan nombres calificados con
    `red_publicaciones.` para no confundir columnas dentro de las subconsultas."""
    try:
        v = int(agencia_id) if agencia_id else 0
    except (TypeError, ValueError):
        v = 0
    if not v:
        return ""
    rp = "red_publicaciones."
    return (f" AND ({rp}agencia_id = {v} OR ("
            f"NOT EXISTS (SELECT 1 FROM red_bloqueos b WHERE b.agencia_id = {rp}agencia_id AND b.bloqueada_id = {v})"
            f" AND (COALESCE({rp}visibilidad, 'todos') = 'todos'"
            f" OR EXISTS (SELECT 1 FROM red_destinos d WHERE d.publicacion_id = {rp}id AND d.agencia_id = {v}))))")
