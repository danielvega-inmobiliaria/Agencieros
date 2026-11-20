"""Créditos de meses gratis (19/11/2026). Como todavía no hay cobro
automático, los meses se anotan acá y se descuentan a mano cuando haya cobro.
Una fila por (agencia, motivo, agencia de origen): no se acredita dos veces.

Motivos:
- 'fundador'              6 meses al Agenciero Fundador de una zona (validado y con stock 30 días).
- 'invitado_fundador'     +1 mes a quien invitó, cuando su colega es validado como fundador de su zona.
- 'invitado_contrato'     +1 mes a quien invitó, con el primer pago del colega.
- 'prueba_zona_cubierta'  1 mes de prueba al colega invitado que cae en una zona ya cubierta.
Sin tope de meses acumulados.
"""
from database import query, execute

MOTIVOS = {
    "fundador": "Agenciero Fundador de su zona",
    "invitado_fundador": "Un colega invitado fue validado como fundador",
    "invitado_contrato": "Un colega invitado contrató",
    "prueba_zona_cubierta": "Mes de prueba (zona ya cubierta)",
}


def acreditar(agencia_id, meses, motivo, origen_agencia_id=0, detalle=None):
    """Anota meses gratis. Devuelve True si los anotó, False si ya estaban."""
    if not agencia_id or meses <= 0:
        return False
    ya = query("SELECT 1 FROM creditos_meses WHERE agencia_id = ? AND motivo = ? AND origen_agencia_id = ?",
               (agencia_id, motivo, origen_agencia_id or 0), one=True)
    if ya:
        return False
    execute("""INSERT INTO creditos_meses (agencia_id, meses, motivo, origen_agencia_id, detalle)
               VALUES (?, ?, ?, ?, ?)""", (agencia_id, meses, motivo, origen_agencia_id or 0, detalle))
    return True


def total(agencia_id):
    fila = query("SELECT COALESCE(SUM(meses), 0) AS m FROM creditos_meses WHERE agencia_id = ?",
                 (agencia_id,), one=True)
    return int(fila["m"] or 0)
