"""Usuarios por agencia y roles (28/09/2026).

- 'dueno': ve y hace todo en su agencia, incluido crear usuarios.
- 'vendedor': usa la app, pero no ve costos ni ganancia (valor de compra,
  gastos, rentabilidad), ni Finanzas, ni Admin, ni Usuarios.
"""
from flask import session

ROLES = {"dueno": "Dueño", "vendedor": "Vendedor"}

# Blueprints / endpoints que un vendedor no puede abrir.
BLUEPRINTS_SOLO_DUENO = {"finanzas", "admin"}
ENDPOINTS_SOLO_DUENO = {"cuenta.usuarios", "cuenta.usuario_nuevo", "cuenta.usuario_editar"}


def es_vendedor():
    return session.get("usuario_rol") == "vendedor"


def es_dueno():
    return bool(session.get("agencia_id")) and session.get("usuario_rol") != "vendedor"


def usuario_id():
    return session.get("usuario_id")


def nombres_usuarios(agencia_id):
    """{id: nombre} de los usuarios de una agencia (para mostrar quién cargó
    o vendió una unidad)."""
    from database import query
    return {r["id"]: r["nombre"] for r in query(
        "SELECT id, nombre FROM agencia_usuarios WHERE agencia_id = ?", (agencia_id,)
    )}
