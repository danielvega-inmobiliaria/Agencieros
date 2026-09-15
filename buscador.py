"""Buscador compartido por Marca / Modelo / Versión / Año / Km / Rango de
precio — mismo criterio y mismos nombres de campo en Stock (Disponible, Por
ingresar, En reparación) y en Red de Agencieros (pedido de Daniel
15/09/2026, continuación 17).

Continuación 18: además de filtrar dentro de una sola pestaña/tabla, el
buscador de Stock ahora puede buscar en simultáneo en Disponible + Por
ingresar + En reparación + Red de Agencieros y devolver todo junto en una
sola lista ordenada por origen (ver `buscar_combinado`), para no tener que
repetir la misma búsqueda pestaña por pestaña. Año pasó a ser un piso ("Año
desde") en vez de una coincidencia exacta."""

CAMPOS_BASE = ["marca", "modelo", "version", "anio", "km_max", "precio_min", "precio_max"]

# Orden y etiquetas de origen para la búsqueda combinada — el orden de esta
# lista es el orden en el que se listan los resultados.
ORDEN_ORIGEN = ["disponible", "por_ingresar", "en_reparacion", "red_ofrece", "red_busca"]
ORIGEN_LABEL = {
    "disponible": "Disponible",
    "por_ingresar": "Por ingresar",
    "en_reparacion": "En reparación",
    "red_ofrece": "Red · Ofrece",
    "red_busca": "Red · Busca",
}
# Reutiliza las clases de badge que ya existen (verde/amarillo/rojo) para no
# introducir una paleta nueva — mismo criterio que usa hoy red/index.html
# para "Ofrece" (verde) / "Busca" (amarillo).
ORIGEN_BADGE = {
    "disponible": "disponible",
    "por_ingresar": "por_ingresar",
    "en_reparacion": "en_reparacion",
    "red_ofrece": "disponible",
    "red_busca": "por_ingresar",
}


def parsear_filtros(args):
    """Lee los parámetros de búsqueda desde `request.args` (o cualquier
    dict tipo `args.get`) una sola vez, y devuelve solo los campos con
    valor cargado y válido — año/km/precio que no convierten a número se
    descartan acá (antes de armar cualquier condición SQL), así nunca se
    arma una condición sin su parámetro correspondiente."""
    filtros = {c: (args.get(c) or "").strip() for c in CAMPOS_BASE}
    filtros = {k: v for k, v in filtros.items() if v}
    for campo, conv in (("anio", int), ("km_max", int), ("precio_min", float), ("precio_max", float)):
        if campo in filtros:
            try:
                filtros[campo] = conv(filtros[campo])
            except ValueError:
                filtros.pop(campo, None)
    return filtros


def condiciones_sql(filtros, campo_precio="valor_publicado", campo_km="km"):
    """A partir de un dict de filtros ya parseado (`parsear_filtros`), arma
    condiciones + params para un WHERE armado a mano (`" AND
    ".join(condiciones)`). `campo_precio` existe porque Stock usa
    `valor_publicado` y Red usa `precio`. Marca/Modelo/Versión son
    coincidencia parcial (LIKE), Año es un piso ("Año desde": `anio >= ?`,
    no exacto), Km es un techo ("Km hasta") y el precio es un rango con
    mínimo y/o máximo opcionales."""
    condiciones, params = [], []
    if filtros.get("marca"):
        condiciones.append("marca LIKE ?")
        params.append(f"%{filtros['marca']}%")
    if filtros.get("modelo"):
        condiciones.append("modelo LIKE ?")
        params.append(f"%{filtros['modelo']}%")
    if filtros.get("version"):
        condiciones.append("version LIKE ?")
        params.append(f"%{filtros['version']}%")
    if "anio" in filtros:
        condiciones.append("anio >= ?")
        params.append(filtros["anio"])
    if "km_max" in filtros:
        condiciones.append(f"{campo_km} <= ?")
        params.append(filtros["km_max"])
    if "precio_min" in filtros:
        condiciones.append(f"{campo_precio} >= ?")
        params.append(filtros["precio_min"])
    if "precio_max" in filtros:
        condiciones.append(f"{campo_precio} <= ?")
        params.append(filtros["precio_max"])
    return condiciones, params


def buscar_combinado(filtros):
    """Un solo buscador para Disponible + Por ingresar + En reparación
    (Stock, sin Vendido) + Red de Agencieros — pedido de Daniel 15/09/2026
    (continuación 18): que buscar no dependa de estar parado en una pestaña
    puntual. Devuelve una lista de dicts ya normalizados (mismas claves
    para un vehículo propio que para una publicación de la Red) y ordenados
    por origen según ORDEN_ORIGEN: Disponible, Por ingresar, En reparación,
    Red (primero lo que otras agencias Ofrecen, después lo que Buscan)."""
    # Import acá adentro (no al tope del módulo) para evitar un import
    # circular: database.py no depende de este módulo, pero varias rutas
    # importan buscador antes que database en el arranque de la app.
    from database import query

    cond_stock, params_stock = condiciones_sql(filtros, campo_precio="valor_publicado", campo_km="km")
    cond_stock.append("estado IN ('disponible','por_ingresar','en_reparacion')")
    vehiculos = query(
        f"SELECT * FROM vehiculos WHERE {' AND '.join(cond_stock)} ORDER BY created_at DESC",
        tuple(params_stock),
    )

    cond_red, params_red = condiciones_sql(filtros, campo_precio="precio", campo_km="km")
    cond_red.append("estado = 'activo'")
    publicaciones = query(
        f"SELECT * FROM red_publicaciones WHERE {' AND '.join(cond_red)} ORDER BY created_at DESC",
        tuple(params_red),
    )

    por_origen = {clave: [] for clave in ORDEN_ORIGEN}
    for v in vehiculos:
        por_origen[v["estado"]].append({
            "origen": v["estado"],
            "marca": v["marca"], "modelo": v["modelo"], "version": v["version"],
            "anio": v["anio"], "km": v["km"], "precio": v["valor_publicado"],
            "ver_endpoint": "stock.detalle", "ver_id": v["id"],
            "agencia": None, "contacto": None,
        })
    for p in publicaciones:
        origen = "red_ofrece" if p["tipo"] == "ofrezco" else "red_busca"
        por_origen[origen].append({
            "origen": origen,
            "marca": p["marca"], "modelo": p["modelo"], "version": p["version"],
            "anio": p["anio"], "km": p["km"], "precio": p["precio"],
            "ver_endpoint": None, "ver_id": None,
            "agencia": p["agencia_nombre"], "contacto": p["contacto"],
        })

    resultados = []
    for clave in ORDEN_ORIGEN:
        for item in por_origen[clave]:
            item["origen_label"] = ORIGEN_LABEL[clave]
            item["origen_badge"] = ORIGEN_BADGE[clave]
            resultados.append(item)
    return resultados
