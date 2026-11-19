"""Invitar a un colega (19/11/2026).

Cada agencia tiene un código propio (`agencias.ref_codigo`) y un link
`/registro?ref=CODIGO`. Quien se inscribe con ese link queda anotado en
`referidos`. El premio (1 mes gratis para quien invitó) se acredita cuando el
colega hace su PRIMER PAGO: como todavía no se cobra desde la app, el admin lo
marca a mano en el Panel de Agencias (ficha del colega → «Registrar primer
pago»). Los meses se anotan como crédito, con tope MAX_MESES_CREDITO.
"""
import secrets

from database import query, execute

MAX_MESES_CREDITO = 6   # tope propuesto: a confirmar por Daniel
MESES_POR_REFERIDO = 1
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


def registrar(invitador_id, invitado_id):
    """Anota que `invitado_id` se inscribió con el link de `invitador_id`."""
    if not invitador_id or invitador_id == invitado_id:
        return
    execute("INSERT OR IGNORE INTO referidos (invitador_id, invitado_id) VALUES (?, ?)",
            (invitador_id, invitado_id))


def meses_acreditados(invitador_id):
    fila = query("SELECT COALESCE(SUM(credito_meses), 0) AS m FROM referidos WHERE invitador_id = ?",
                 (invitador_id,), one=True)
    return int(fila["m"] or 0)


def acreditar_primer_pago(invitado_id):
    """Marca el primer pago del colega y acredita meses a quien lo invitó.
    Devuelve (ok, mensaje). Idempotente: no acredita dos veces."""
    r = query("SELECT * FROM referidos WHERE invitado_id = ?", (invitado_id,), one=True)
    if r is None:
        return False, "Esta agencia no llegó por una invitación."
    if r["pago_at"]:
        return False, "El primer pago ya estaba registrado."
    ya = meses_acreditados(r["invitador_id"])
    meses = max(0, min(MESES_POR_REFERIDO, MAX_MESES_CREDITO - ya))
    execute("UPDATE referidos SET pago_at = datetime('now'), credito_meses = ? WHERE id = ?",
            (meses, r["id"]))
    if meses:
        return True, f"Primer pago registrado: se acreditó {meses} mes gratis a quien la invitó."
    return True, f"Primer pago registrado. Quien la invitó ya llegó al tope de {MAX_MESES_CREDITO} meses: no se suma crédito."


def lista_de(invitador_id):
    return query(
        """SELECT r.created_at, r.pago_at, r.credito_meses, a.nombre_agencia, a.email_verificado,
                  (SELECT c.ciudad FROM agencia_config c WHERE c.agencia_id = a.id) AS ciudad_txt
           FROM referidos r JOIN agencias a ON a.id = r.invitado_id
           WHERE r.invitador_id = ? ORDER BY r.created_at DESC""",
        (invitador_id,),
    )
