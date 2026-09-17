"""
Filtra el texto libre del campo `vehiculos.equipamiento` para la ficha
comercial (`stock.ficha`) -- ese campo se llena de 2 formas muy distintas y
ninguna de las 2 es directamente publicable tal cual:

  1. Desde la Toma técnica (`_texto_equipamiento` en routes/tomas.py): vuelca
     los 25 puntos del grupo "Accesorios y equipamiento" CON su calificación,
     incluidos los que están mal o no tiene el auto -- ej. "Cámara
     retrovisora (No posee)". Perfecto para uso interno, pésimo para
     mostrarle al comprador (le estás avisando defectos y anunciando cosas
     que el auto no tiene).
  2. Desde `sync_stock.py` (parseando la ficha de AGENCIA INGRESOS): ya viene
     una lista corta y curada a mano ("Tapizado de cuero, Aire
     acondicionado, ..."), sin calificaciones -- esa se puede mostrar tal
     cual.

Esta función distingue un caso del otro y en el caso 1 se queda solo con los
puntos calificados Bueno/Excelente que además son un plus real de cara al
comprador (no cosas obligatorias/básicas como Documentación o Cinturones de
seguridad, que no suman como argumento de venta) -- pedido de Daniel
17/09/2026 al ver la ficha con "Cámara retrovisora (No posee)" mostrada como
si fuera un dato comercial.
"""
import re

# Códigos de GRUPO_ACCESORIOS (routes/tomas.py) que sí son un plus de cara al
# comprador. Se dejan afuera a propósito los básicos/obligatorios: batería,
# documentación, electricidad (general), luces, limpiaparabrisas, parabrisas,
# regulación de altura de faros, cinturones de seguridad, criket, llave de
# ruedas, manuales, duplicado de llave -- ninguno vende un auto, son cosas
# que se esperan de mínima.
_CODIGOS_DESTACABLES = {
    "aire_acondicionado", "levantavidrios", "espejos_electricos", "techo_corredizo",
    "luneta_termica", "cierre_electrico", "calefactor", "computadora_reloj",
    "control_satelital", "parlantes", "radio_cd_usb", "camara_retrovisora",
    "sensores_estacionamiento",
}
_CALIFICACIONES_POSITIVAS = {"bueno", "excelente"}


def _labels_destacables():
    from routes.tomas import GRUPO_ACCESORIOS
    return {label for codigo, label in GRUPO_ACCESORIOS if codigo in _CODIGOS_DESTACABLES}


def equipamiento_destacado(texto, limite=8):
    """Devuelve una lista corta (máx `limite`) de ítems de equipamiento
    listos para mostrar en la ficha comercial, ya filtrados."""
    if not texto:
        return []

    lineas = [l.strip() for l in texto.replace("\r", "").split("\n") if l.strip()]
    labels_ok = _labels_destacables()
    resultado = []
    algun_formato_checklist = False

    for linea in lineas:
        m = re.match(r"^(.+?)\s*\((.+?)\)(?::.*)?$", linea)
        if m:
            algun_formato_checklist = True
            label, calificacion = m.group(1).strip(), m.group(2).strip().lower()
            if calificacion in _CALIFICACIONES_POSITIVAS and label in labels_ok:
                resultado.append(label)

    if algun_formato_checklist:
        return resultado[:limite]

    # No tiene formato "Label (Calificación)" -- viene ya curado a mano
    # (ej. sincronizado desde AGENCIA INGRESOS), se muestra tal cual.
    items = [i.strip() for linea in lineas for i in linea.split(",") if i.strip()]
    return items[:limite]
