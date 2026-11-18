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
from database import query, execute

MIN_VEHICULOS = 10  # unidades que tienen que cumplir cada consigna

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
