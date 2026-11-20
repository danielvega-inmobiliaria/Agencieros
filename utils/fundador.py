"""Campaña «Agenciero Fundador» (17/11/2026).

Premio: 6 meses gratis del plan para la primera agencia de cada zona (barrio
de Rosario o localidad del Gran Rosario) que cumpla las consignas de la
misión. Se lanza con 3 consignas; la 4.ª (portal público de la Red) se
acredita cuando el portal exista. Sin fecha de cierre.

- Las zonas viven en la tabla `zonas` (se cargan desde
  ZONAS_CAMPANA_FUNDADOR.csv en database._migrar_zonas_fundador).
- Cada agencia elige su zona en Registro o en Admin (agencia_config.zona_id).
- Al completar las 3 consignas se guarda `agencias.mision_completada_at`
  (UTC); si la zona todavía no tiene fundador, queda esta agencia como
  fundador PROVISORIO (la validación del admin viene en el panel de
  fundadores, todavía sin hacer). Los meses se anotan como crédito: todavía
  no hay cobro automático.
"""
from datetime import datetime

from database import query, execute
from utils import creditos

MIN_VEHICULOS = 10  # unidades que tienen que cumplir cada consigna
DIAS_STOCK = 30     # días que tiene que sostener la misión antes de acreditar el premio

# Orden en que se muestran los grupos del selector de zona.
_ORDEN_DISTRITOS = ["Centro", "Norte", "Noroeste", "Oeste", "Sudoeste", "Sur"]


def zonas_agrupadas():
    """Zonas activas agrupadas para un <select> con <optgroup>: los barrios
    de Rosario por distrito y las localidades del Gran Rosario al final."""
    grupos = {}
    for z in query("SELECT id, nombre, tipo, distrito FROM zonas WHERE activa = 1 ORDER BY nombre"):
        if str(z["tipo"]).startswith("localidad"):
            clave = "Gran Rosario (localidades)"
        else:
            clave = f"Rosario · Distrito {z['distrito']}"
        grupos.setdefault(clave, []).append(z)

    def _orden(item):
        clave = item[0]
        if clave.startswith("Rosario · Distrito "):
            d = clave.replace("Rosario · Distrito ", "")
            return (0, _ORDEN_DISTRITOS.index(d) if d in _ORDEN_DISTRITOS else 99)
        return (1, 0)

    return sorted(grupos.items(), key=_orden)


def zona_valida(valor):
    """Devuelve el id de zona si existe y está activa; si no, None."""
    try:
        zid = int(valor)
    except (TypeError, ValueError):
        return None
    fila = query("SELECT id FROM zonas WHERE id = ? AND activa = 1", (zid,), one=True)
    return fila["id"] if fila else None


def progreso(agencia_id):
    """Estado de la misión de una agencia, o None si no corresponde mostrarla
    (agencia demo). Devuelve zona, consignas, % y si ya la completó."""
    ag = query("SELECT id, es_demo, web_activa, mision_completada_at FROM agencias WHERE id = ?",
               (agencia_id,), one=True)
    if not ag or ag["es_demo"]:
        return None
    cfg = query("SELECT zona_id FROM agencia_config WHERE agencia_id = ?", (agencia_id,), one=True)
    zona = None
    if cfg and cfg["zona_id"]:
        zona = query("SELECT * FROM zonas WHERE id = ?", (cfg["zona_id"],), one=True)

    cargados = query(
        "SELECT COUNT(*) c FROM vehiculos WHERE agencia_id = ? AND estado != 'vendido'",
        (agencia_id,), one=True)["c"]
    en_red = query(
        """SELECT COUNT(DISTINCT vehiculo_id) c FROM red_publicaciones
           WHERE agencia_id = ? AND estado = 'activo' AND vehiculo_id IS NOT NULL""",
        (agencia_id,), one=True)["c"]
    en_web = 0
    if ag["web_activa"]:
        en_web = query(
            """SELECT COUNT(*) c FROM vehiculos
               WHERE agencia_id = ? AND estado = 'disponible' AND COALESCE(web_visible, 1) = 1""",
            (agencia_id,), one=True)["c"]

    consignas = [
        {"clave": "cargados", "texto": f"Tener al menos {MIN_VEHICULOS} vehículos cargados en Stock",
         "n": cargados, "ok": cargados >= MIN_VEHICULOS, "url": "stock.index"},
        {"clave": "red", "texto": f"Compartir al menos {MIN_VEHICULOS} vehículos en la Red",
         "n": en_red, "ok": en_red >= MIN_VEHICULOS, "url": "stock.index"},
        {"clave": "web", "texto": f"Tener al menos {MIN_VEHICULOS} vehículos visibles en tu web",
         "n": en_web, "ok": en_web >= MIN_VEHICULOS, "url": "web_agencia.config" },
    ]
    hecho = sum(min(c["n"], MIN_VEHICULOS) for c in consignas)
    pct = round(hecho * 100 / (MIN_VEHICULOS * len(consignas)))
    completa = all(c["ok"] for c in consignas)
    return {
        "zona": zona,
        "consignas": consignas,
        "pct": pct,
        "completa": completa,
        "completada_at": ag["mision_completada_at"],
        "es_fundador": bool(zona and zona["fundador_agencia_id"] == agencia_id),
        "validado": bool(zona and zona["fundador_agencia_id"] == agencia_id and zona["fundador_validado_at"]),
        "premiado": bool(zona and zona["fundador_agencia_id"] == agencia_id and zona["fundador_premio_at"]),
        "zona_tomada": bool(zona and zona["fundador_agencia_id"]
                            and zona["fundador_agencia_id"] != agencia_id),
        "premio_meses": (zona["premio_meses"] if zona else 6),
    }


def registrar_si_completa(agencia_id):
    """Si la agencia cumple las 3 consignas y tiene zona, guarda la fecha de
    misión completada (una sola vez) y, si la zona todavía no tiene
    fundador, la deja como fundador provisorio. Devuelve el progreso
    actualizado."""
    p = progreso(agencia_id)
    if not p or not p["zona"] or not p["completa"] or p["completada_at"]:
        return p
    execute("UPDATE agencias SET mision_completada_at = datetime('now') WHERE id = ? AND mision_completada_at IS NULL",
            (agencia_id,))
    execute("""UPDATE zonas SET fundador_agencia_id = ?, fundador_fecha = datetime('now')
               WHERE id = ? AND fundador_agencia_id IS NULL""", (agencia_id, p["zona"]["id"]))
    return progreso(agencia_id)


# ---------------------------------------------------------------------------
# Reglas confirmadas por Daniel (19/11/2026)
#  - La primera agencia de la zona que cumple la misión queda como fundador
#    PROVISORIO (registrar_si_completa).
#  - El admin lo VALIDA (agencia real, fotos propias, sin duplicados): desde ahí
#    la zona está «cubierta» y aparece el sello. Si quien lo invitó existe, suma
#    +1 mes en ese momento.
#  - Los 6 meses se acreditan cuando pasaron 30 días desde que cumplió la misión
#    y sigue cumpliéndola.
# ---------------------------------------------------------------------------

def _dias_desde(ts):
    if not ts:
        return None
    try:
        return max(0, (datetime.utcnow() - datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S")).days)
    except ValueError:
        return None


def estado_zona(z):
    """libre | provisorio | validado | premiado."""
    if not z["fundador_agencia_id"]:
        return "libre"
    if z["fundador_premio_at"]:
        return "premiado"
    if z["fundador_validado_at"]:
        return "validado"
    return "provisorio"


def zonas_panel():
    """Zonas con fundador (provisorio, validado o premiado) para el panel del admin."""
    filas = query(
        """SELECT z.*, a.nombre_agencia AS fundador_nombre, a.email AS fundador_email,
                  a.mision_completada_at AS completada_at
           FROM zonas z JOIN agencias a ON a.id = z.fundador_agencia_id
           WHERE z.activa = 1 ORDER BY z.fundador_validado_at IS NOT NULL, a.mision_completada_at""")
    salida = []
    for z in filas:
        d = dict(z)
        d["estado"] = estado_zona(z)
        d["dias"] = _dias_desde(z["completada_at"])
        ok, motivo = _puede_acreditar(z)
        d["puede_acreditar"] = ok
        d["motivo_no"] = motivo
        salida.append(d)
    return salida


def _puede_acreditar(z):
    """(se puede acreditar ya?, motivo si no) para el panel del admin."""
    if z["fundador_premio_at"]:
        return False, "Ya acreditado."
    if not z["fundador_validado_at"]:
        return False, "Primero hay que validarla."
    dias = _dias_desde(z["completada_at"])
    if dias is None or dias < DIAS_STOCK:
        return False, f"Faltan {DIAS_STOCK - (dias or 0)} días de stock sostenido."
    return True, ""


def validar_fundador(zona_id):
    """El admin valida al fundador provisorio: la zona queda cubierta."""
    z = query("SELECT * FROM zonas WHERE id = ?", (zona_id,), one=True)
    if not z or not z["fundador_agencia_id"]:
        return False, "Esa zona no tiene fundador para validar."
    if z["fundador_validado_at"]:
        return False, "Ese fundador ya estaba validado."
    execute("UPDATE zonas SET fundador_validado_at = datetime('now') WHERE id = ?", (zona_id,))
    ref = query("SELECT invitador_id FROM referidos WHERE invitado_id = ?", (z["fundador_agencia_id"],), one=True)
    extra = ""
    if ref and creditos.acreditar(ref["invitador_id"], 1, "invitado_fundador", z["fundador_agencia_id"]):
        extra = " Se sumó 1 mes a quien lo invitó."
    return True, f"Fundador de {z['nombre']} validado: la zona queda cubierta y la agencia recibe el sello.{extra}"


def rechazar_fundador(zona_id):
    """El admin rechaza al fundador (no era una agencia real, duplicada, etc.):
    pasa a la siguiente agencia de la zona que cumplió la misión, si hay."""
    z = query("SELECT * FROM zonas WHERE id = ?", (zona_id,), one=True)
    if not z or not z["fundador_agencia_id"]:
        return False, "Esa zona no tiene fundador."
    if z["fundador_premio_at"]:
        return False, "El premio ya se acreditó: no se puede rechazar."
    sig = query(
        """SELECT a.id FROM agencias a JOIN agencia_config c ON c.agencia_id = a.id
           WHERE c.zona_id = ? AND a.id != ? AND a.activo = 1 AND a.mision_completada_at IS NOT NULL
           ORDER BY a.mision_completada_at LIMIT 1""", (zona_id, z["fundador_agencia_id"]), one=True)
    execute("""UPDATE zonas SET fundador_agencia_id = ?, fundador_fecha = datetime('now'),
               fundador_validado_at = NULL WHERE id = ?""", (sig["id"] if sig else None, zona_id))
    if sig:
        return True, f"Fundador rechazado: pasa a la siguiente agencia de {z['nombre']} que cumplió la misión (queda provisoria)."
    return True, f"Fundador rechazado: {z['nombre']} queda libre."


def acreditar_premio(zona_id):
    """Acredita los meses al fundador validado, si pasaron DIAS_STOCK días desde
    que cumplió la misión y la sigue cumpliendo."""
    z = query("SELECT * FROM zonas WHERE id = ?", (zona_id,), one=True)
    if not z or not z["fundador_agencia_id"]:
        return False, "Esa zona no tiene fundador."
    if z["fundador_premio_at"]:
        return False, "El premio ya estaba acreditado."
    if not z["fundador_validado_at"]:
        return False, "Primero hay que validar al fundador."
    ag_id = z["fundador_agencia_id"]
    ag = query("SELECT mision_completada_at FROM agencias WHERE id = ?", (ag_id,), one=True)
    dias = _dias_desde(ag["mision_completada_at"]) if ag else None
    if dias is None or dias < DIAS_STOCK:
        faltan = DIAS_STOCK - (dias or 0)
        return False, f"Todavía no pasaron {DIAS_STOCK} días desde que cumplió la misión (faltan {faltan})."
    p = progreso(ag_id)
    if not p or not p["completa"]:
        return False, "Hoy ya no cumple las 3 consignas (bajó su stock): no se acredita."
    creditos.acreditar(ag_id, z["premio_meses"], "fundador", 0, f"Fundador de {z['nombre']}")
    execute("UPDATE zonas SET fundador_premio_at = datetime('now') WHERE id = ?", (zona_id,))
    return True, f"Se acreditaron {z['premio_meses']} meses gratis al fundador de {z['nombre']}."
