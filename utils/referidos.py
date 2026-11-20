"""Invitar a un colega (19/11/2026).

Cada agencia tiene un código propio (`agencias.ref_codigo`) y un link
`/registro?ref=CODIGO`. Quien se inscribe con ese link queda anotado en
`referidos`. El premio (1 mes gratis para quien invitó) se acredita cuando el
colega hace su PRIMER PAGO: como todavía no se cobra desde la app, el admin lo
marca a mano en el Panel de Agencias (ficha del colega → «Registrar primer
pago»). Los meses se anotan como crédito, sin tope.
"""
import secrets

from database import query, execute
from utils import creditos

MESES_POR_REFERIDO = 1   # sin tope de meses acumulados (Daniel, 19/11/2026)
_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin O/0/I/1


def codigo_de(agencia_id):
    """Devuelve el código de invitación de la agencia (lo crea si no tiene)."""
    fila = query("SELECT ref_codigo FROM agencias WHERE id = ?", (agencia_id,), one=True)
    if fila is None:
        return None
    if fila["ref_codigo"]:
        return fila["ref_codigo"]
    for _ in range(20):
        cod = "".join(secrets.choice(_ALFABETO) for _ in range(6))
        if not query("SELECT 1 FROM agencias WHERE ref_codigo = ?", (cod,), one=True):
            execute("UPDATE agencias SET ref_codigo = ? WHERE id = ?", (cod, agencia_id))
            return cod
    return None


def agencia_por_codigo(codigo):
    """Id de la agencia dueña del código, o None."""
    cod = (codigo or "").strip().upper()
    if not cod or len(cod) > 12:
        return None
    fila = query("SELECT id FROM agencias WHERE ref_codigo = ? AND activo = 1", (cod,), one=True)
    return fila["id"] if fila else None


def registrar(invitador_id, invitado_id, zona_id=None):
    """Anota que `invitado_id` se inscribió con el link de `invitador_id`.
    Si su zona ya está cubierta (tiene un fundador validado por el admin), el
    colega recibe 1 mes de prueba; vale también si es la zona de quien lo
    invitó (decidido por Daniel el 19/11/2026)."""
    if not invitador_id or invitador_id == invitado_id:
        return
    execute("INSERT OR IGNORE INTO referidos (invitador_id, invitado_id) VALUES (?, ?)",
            (invitador_id, invitado_id))
    if zona_id:
        z = query("SELECT fundador_agencia_id, fundador_validado_at FROM zonas WHERE id = ?", (zona_id,), one=True)
        if z and z["fundador_validado_at"] and z["fundador_agencia_id"] != invitado_id:
            creditos.acreditar(invitado_id, 1, "prueba_zona_cubierta", invitador_id)


def meses_acreditados(agencia_id):
    """Meses gratis acumulados por la agencia (todos los motivos, sin tope)."""
    return creditos.total(agencia_id)


def acreditar_primer_pago(invitado_id):
    """Marca el primer pago del colega y acredita meses a quien lo invitó.
    Devuelve (ok, mensaje). Idempotente: no acredita dos veces."""
    r = query("SELECT * FROM referidos WHERE invitado_id = ?", (invitado_id,), one=True)
    if r is None:
        return False, "Esta agencia no llegó por una invitación."
    if r["pago_at"]:
        return False, "El primer pago ya estaba registrado."
    meses = MESES_POR_REFERIDO
    execute("UPDATE referidos SET pago_at = datetime('now'), credito_meses = ? WHERE id = ?",
            (meses, r["id"]))
    creditos.acreditar(r["invitador_id"], meses, "invitado_contrato", invitado_id)
    return True, f"Primer pago registrado: se acreditó {meses} mes gratis a quien la invitó."


def lista_de(invitador_id):
    """Invitados con su actividad (para que quien invita sepa quién la usa y
    pueda insistirle): mail validado, autos cargados / en stock y última vez
    que entró."""
    return query(
        """SELECT r.created_at, r.pago_at, r.credito_meses, a.nombre_agencia, a.email_verificado,
                  a.telefono, a.ultima_actividad,
                  (SELECT c.ciudad FROM agencia_config c WHERE c.agencia_id = a.id) AS ciudad_txt,
                  (SELECT COUNT(*) FROM vehiculos v WHERE v.agencia_id = a.id) AS autos,
                  (SELECT COUNT(*) FROM vehiculos v WHERE v.agencia_id = a.id AND v.estado = 'disponible') AS autos_stock
           FROM referidos r JOIN agencias a ON a.id = r.invitado_id
           WHERE r.invitador_id = ? ORDER BY r.created_at DESC""",
        (invitador_id,),
    )
