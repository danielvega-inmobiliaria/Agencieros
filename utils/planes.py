"""Planes por agencia y sus límites (30/09/2026, paso 5 de "reorganizar
cuentas y Red"). Decidido por Daniel el 30/09/2026:

| plan          | usuarios        | unidades | sucursales | publicar en la Red |
|---------------|-----------------|----------|------------|--------------------|
| agenciero     | 1               | 15       | no         | 3                  |
| agencia       | 1 dueño + 2 vend| 30       | no         | 6                  |
| multisucursal | ilimitados      | ilim.    | 2          | ilimitado          |
| libre         | sin límites (lanzamiento: todas las agencias arrancan acá)   |

- Precios decididos (no se publican por ahora): $24.990 (a confirmar) /
  $49.990 / $74.990. No se muestran en la app.
- Consulta de precios, Stock, Toma, seña/venta, Pedidos, Financiación y
  VER la Red: iguales en todos los planes.
- Red: cuenta solo lo que la agencia OFRECE activo (unidades de Stock en la
  Red + publicaciones manuales "Ofrezco"). Las búsquedas ("Busco") son
  libres: suman movimiento a la Red sin costo.
- Si una agencia ya está por encima del límite (le bajaron el plan), no se
  borra nada: solo no puede agregar más hasta volver a estar por debajo.
- El plan lo cambia el admin desde el Panel de Agencias. Sin cobro
  automático todavía.
"""
from database import query

PLAN_DEFAULT = "libre"

PLANES = {
    "libre": {"nombre": "Libre (lanzamiento)", "usuarios": None, "unidades": None, "sucursales": None, "red": None},
    "agenciero": {"nombre": "Agenciero", "usuarios": 1, "unidades": 15, "sucursales": 0, "red": 3},
    "agencia": {"nombre": "Agencia", "usuarios": 3, "unidades": 30, "sucursales": 0, "red": 6},
    "multisucursal": {"nombre": "Multisucursal", "usuarios": None, "unidades": None, "sucursales": 2, "red": None},
}

RECURSOS = {
    "usuarios": "usuarios activos",
    "unidades": "unidades en stock",
    "sucursales": "sucursales",
    "red": "publicaciones en la Red",
}


def plan_de(agencia_id):
    fila = query("SELECT plan FROM agencias WHERE id = ?", (agencia_id,), one=True)
    clave = (fila["plan"] if fila else None) or PLAN_DEFAULT
    return clave if clave in PLANES else PLAN_DEFAULT


def uso(agencia_id):
    """Cuánto usa hoy la agencia de cada recurso limitado."""
    return {
        "usuarios": query("SELECT COUNT(*) c FROM agencia_usuarios WHERE agencia_id = ? AND activo = 1",
                          (agencia_id,), one=True)["c"],
        "unidades": query("SELECT COUNT(*) c FROM vehiculos WHERE agencia_id = ? AND estado != 'vendido'",
                          (agencia_id,), one=True)["c"],
        "sucursales": query("SELECT COUNT(*) c FROM sucursales WHERE agencia_id = ? AND activa = 1",
                            (agencia_id,), one=True)["c"],
        "red": query(
            """SELECT COUNT(*) c FROM red_publicaciones
               WHERE agencia_id = ? AND estado = 'activo' AND COALESCE(tipo, 'ofrezco') != 'busco'""",
            (agencia_id,), one=True)["c"],
    }


def limite(agencia_id, recurso):
    return PLANES[plan_de(agencia_id)][recurso]


def puede_agregar(agencia_id, recurso, cantidad=1):
    """(True, None) o (False, mensaje para mostrar)."""
    tope = limite(agencia_id, recurso)
    if tope is None:
        return True, None
    actual = uso(agencia_id)[recurso]
    if actual + cantidad <= tope:
        return True, None
    nombre = PLANES[plan_de(agencia_id)]["nombre"]
    if tope == 0:
        msg = f"Tu plan {nombre} no incluye {RECURSOS[recurso]}."
    else:
        msg = f"Llegaste al máximo de tu plan {nombre}: {tope} {RECURSOS[recurso]} (hoy tenés {actual})."
    return False, msg + " Para ampliarlo escribinos desde «Consultas y avisos»."


def resumen(agencia_id):
    """Plan + uso + tope de cada recurso, para Mi cuenta y el Panel."""
    clave = plan_de(agencia_id)
    p = PLANES[clave]
    u = uso(agencia_id)
    return {
        "clave": clave, "nombre": p["nombre"],
        "items": [
            {"recurso": r, "label": RECURSOS[r], "uso": u[r], "tope": p[r],
             "excedido": p[r] is not None and u[r] > p[r]}
            for r in RECURSOS
        ],
    }
