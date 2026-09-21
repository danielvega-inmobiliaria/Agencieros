"""Buscador compartido por Marca / Modelo / Versión / Año — mismo criterio
y mismos nombres de campo en Stock (Disponible, Por ingresar, En
reparación), Pedidos y Red de Agencieros (pedido de Daniel 15/09/2026,
continuación 17).

Continuación 18: además de filtrar dentro de una sola pestaña/tabla, el
buscador de Stock ahora puede buscar en simultáneo en Disponible + Por
ingresar + En reparación + Red de Agencieros y devolver todo junto en una
sola lista ordenada por origen (ver `buscar_combinado`), para no tener que
repetir la misma búsqueda pestaña por pestaña.

Continuación 26: se suma una quinta fuente, "Posible entrega" — el
vehículo que un cliente ya ofreció como parte de pago (permuta) en otro
pedido activo, todavía sin llegar físicamente al stock. Así, tanto el
buscador de Stock como el chequeo automático al cargar un pedido nuevo
tienen en cuenta la máxima cantidad de fuentes posibles: Disponible, Por
ingresar, En reparación, Red · Ofrece y Posible entrega.

Rediseño 21/09/2026 (pedido de Daniel, escalado de Finanzas/Financiación/
Matches): Año dejó de ser un piso ("Año desde") -- ahora matchea el año
exacto o ±1, para tener una opción más amplia. Versión salió del criterio
por defecto: solo se exige (y de forma exacta, no parcial) si se tilda el
checkbox "versión exacta" en el buscador -- así un vehículo cargado con
versión específica se puede encontrar después a propósito, sin que la
versión angoste todas las demás búsquedas. Precio y Km dejaron de ser
criterio de matching en cualquiera de estos lugares (Stock, Pedidos, Red):
se siguen mostrando en los resultados, pero ya no filtran nada."""

CAMPOS_BASE = ["marca", "modelo", "version", "anio"]

# Orden y etiquetas de origen para la búsqueda combinada — el orden de esta
# lista es el orden en el que se listan los resultados.
ORDEN_ORIGEN = ["disponible", "por_ingresar", "en_reparacion", "red_ofrece", "posible_entrega", "red_busca"]
ORIGEN_LABEL = {
    "disponible": "Disponible",
    "por_ingresar": "Por ingresar",
    "en_reparacion": "En reparación",
    "red_ofrece": "Red · Ofrece",
    "posible_entrega": "Posible entrega",
    "red_busca": "Red · Busca",
}
# Reutiliza las clases de badge que ya existen (verde/amarillo/rojo) para no
# introducir una paleta nueva — mismo criterio que usa hoy red/index.html
# para "Ofrece" (verde) / "Busca" (amarillo). "Posible entrega" usa el
# mismo amarillo que "Por ingresar": en los dos casos el auto todavía no
# está físicamente disponible para vender.
ORIGEN_BADGE = {
    "disponible": "disponible",
    "por_ingresar": "por_ingresar",
    "en_reparacion": "en_reparacion",
    "red_ofrece": "disponible",
    "posible_entrega": "por_ingresar",
    "red_busca": "por_ingresar",
}


def parsear_filtros(args):
    """Lee los parámetros de búsqueda desde `request.args` (o cualquier
    dict tipo `args.get`) una sola vez, y devuelve solo los campos con
    valor cargado y válido — año que no convierte a número se descarta acá
    (antes de armar cualquier condición SQL), así nunca se arma una
    condición sin su parámetro correspondiente.

    Km y Precio dejaron de ser filtros de búsqueda (21/09/2026, pedido de
    Daniel): ya no se leen. `version_exacta` es el checkbox "sí o sí" --
    si no está tildado, Versión no entra en `filtros` aunque el campo de
    texto tenga algo cargado (queda solo para mostrar/reusar el valor en el
    form, nunca para filtrar)."""
    filtros = {c: (args.get(c) or "").strip() for c in CAMPOS_BASE}
    filtros = {k: v for k, v in filtros.items() if v}
    if "anio" in filtros:
        try:
            filtros["anio"] = int(filtros["anio"])
        except ValueError:
            filtros.pop("anio", None)
    if str(args.get("version_exacta") or "").lower() in ("on", "1", "true", "si", "sí"):
        filtros["version_exacta"] = True
    return filtros


def condiciones_sql(filtros, campo_precio="valor_publicado", campo_km="km",
                     campo_marca="marca", campo_modelo="modelo",
                     campo_version="version", campo_anio="anio"):
    """A partir de un dict de filtros ya parseado (`parsear_filtros`), arma
    condiciones + params para un WHERE armado a mano (`" AND
    ".join(condiciones)`). `campo_marca`/`campo_modelo`/`campo_version`/
    `campo_anio` existen para poder reutilizar este mismo armador contra una
    tabla con nombres de columna distintos, como `pedidos_clientes`
    filtrando por su vehículo de permuta (`permuta_marca`, etc. — pedido de
    Daniel 15/09/2026, continuación 26). `campo_precio`/`campo_km` quedan en
    la firma solo por compatibilidad con quien ya los pasa -- no se usan.

    Criterio de matching redefinido 21/09/2026 (pedido de Daniel: mismo
    criterio para Stock/Por ingresar/En reparación, Pedidos y Red, es un
    solo buscador compartido): Marca y Modelo son coincidencia parcial
    (LIKE), igual que antes. Año ya no es un piso -- matchea el año exacto
    o ±1, para tener una opción más amplia. Versión queda AFUERA del
    matching salvo que venga `version_exacta` (el checkbox "sí o sí" del
    buscador): ahí sí exige coincidencia exacta, no parcial. Precio y Km
    dejaron de ser criterio en cualquiera de estas búsquedas -- se siguen
    mostrando en los resultados, pero ya no filtran ni excluyen nada."""
    condiciones, params = [], []
    if filtros.get("marca"):
        condiciones.append(f"{campo_marca} LIKE ?")
        params.append(f"%{filtros['marca']}%")
    if filtros.get("modelo"):
        condiciones.append(f"{campo_modelo} LIKE ?")
        params.append(f"%{filtros['modelo']}%")
    if filtros.get("version_exacta") and filtros.get("version"):
        condiciones.append(f"LOWER({campo_version}) = LOWER(?)")
        params.append(filtros["version"])
    if "anio" in filtros:
        condiciones.append(f"{campo_anio} BETWEEN ? AND ?")
        params.append(filtros["anio"] - 1)
        params.append(filtros["anio"] + 1)
    return condiciones, params


def _buscar_posible_entrega(filtros, agencia_id):
    """"Posible entrega": el vehículo que un cliente ya ofreció como parte
    de pago (permuta) en un pedido propio todavía activo (`buscando`), y
    que por lo tanto podría estar disponible pronto aunque todavía no llegó
    físicamente al stock — una fuente más para tener la máxima posibilidad
    de match, tanto buscando en Stock como al cargar un pedido nuevo (pedido
    de Daniel 15/09/2026, continuación 26). No se filtra por precio: el
    vehículo de permuta todavía no tiene un precio de venta asignado.

    Escopeado por `agencia_id` (18/09/2026): son pedidos de clientes de una
    agencia puntual (nombre y teléfono incluidos en el resultado) -- Pedidos
    todavía no es multi-tenant en sus propias rutas, pero esta búsqueda
    combinada de Stock no puede mostrarle datos de un cliente de otra
    agencia."""
    from database import query

    # Precio ya no es criterio de matching (21/09/2026) -- condiciones_sql
    # ni siquiera lo mira, pero se mantiene el nombre de la variable para no
    # tocar el resto de la función.
    filtros_sin_precio = filtros
    condiciones, params = condiciones_sql(
        filtros_sin_precio,
        campo_marca="permuta_marca", campo_modelo="permuta_modelo",
        campo_version="permuta_version", campo_anio="permuta_anio", campo_km="permuta_km",
    )
    condiciones += [
        "agencia_id = ?", "estado = 'buscando'", "forma_pago = 'permuta'",
        "permuta_marca IS NOT NULL", "permuta_marca != ''",
    ]
    params.append(agencia_id)
    return query(
        f"SELECT * FROM pedidos_clientes WHERE {' AND '.join(condiciones)} ORDER BY created_at DESC",
        tuple(params),
    )


def _buscar_posible_entrega_senas(filtros, agencia_id):
    """"Posible entrega" desde una seña abierta con permuta (19/09/2026): el
    vehículo que el cliente va a entregar en permuta al cerrar la venta
    (Stock -> Señar). Todavía no llegó, pero ya se sabe que entra: tiene
    los datos mínimos (Año/Marca/Modelo, Versión y Km si se cargaron) y por
    eso se cruza con los pedidos igual que la permuta de un pedido. Solo
    cuentan las señas abiertas ('senado') y, una vez cerrada la venta, las
    permutas que todavía esperan destino (`permuta_destino` NULL: ingresa a
    Stock o va a reparación, ver stock.permuta_destino): el vehículo ya
    llegó o está por llegar y sigue disponible para matchear hasta que se
    cargue. Si la seña se cancela, deja de serlo."""
    from database import query

    # Precio ya no es criterio de matching (21/09/2026) -- condiciones_sql
    # ni siquiera lo mira, pero se mantiene el nombre de la variable para no
    # tocar el resto de la función.
    filtros_sin_precio = filtros
    condiciones, params = condiciones_sql(
        filtros_sin_precio,
        campo_marca="permuta_marca", campo_modelo="permuta_modelo",
        campo_version="permuta_version", campo_anio="permuta_anio", campo_km="permuta_km",
    )
    condiciones += [
        "agencia_id = ?",
        "(estado = 'senado' OR (estado = 'cerrada' AND permuta_destino IS NULL))",
        "permuta_marca IS NOT NULL", "permuta_marca != ''",
    ]
    params.append(agencia_id)
    return query(
        f"SELECT * FROM ventas WHERE {' AND '.join(condiciones)} ORDER BY created_at DESC",
        tuple(params),
    )


def _buscar_posible_entrega_planes(filtros, agencia_id):
    """"Posible entrega" desde un crédito de Financiación pendiente de firma
    con permuta (19/09/2026): igual que la seña, el vehículo todavía no
    llegó pero ya se sabe que entra (tiene Año/Marca/Modelo). Solo cuentan
    los planes 'pendiente_firma' y, una vez cerrada la operación (plan
    activo/finalizado), los que todavía esperan destino (`permuta_destino`
    NULL: ingresa a Stock o va a reparación). Si se cancela la reserva no
    entra."""
    from database import query

    # Precio ya no es criterio de matching (21/09/2026) -- condiciones_sql
    # ni siquiera lo mira, pero se mantiene el nombre de la variable para no
    # tocar el resto de la función.
    filtros_sin_precio = filtros
    condiciones, params = condiciones_sql(
        filtros_sin_precio,
        campo_marca="permuta_marca", campo_modelo="permuta_modelo",
        campo_version="permuta_version", campo_anio="permuta_anio", campo_km="permuta_km",
    )
    condiciones += [
        "COALESCE(agencia_id, 1) = ?",
        "(estado = 'pendiente_firma' OR (estado IN ('activo', 'finalizado') AND permuta_destino IS NULL))",
        "permuta_marca IS NOT NULL", "permuta_marca != ''",
    ]
    params.append(agencia_id)
    return query(
        f"SELECT * FROM financiaciones WHERE {' AND '.join(condiciones)} ORDER BY created_at DESC",
        tuple(params),
    )


def buscar_combinado(filtros, agencia_id):
    """Un solo buscador para Disponible + Por ingresar + En reparación
    (Stock, sin Vendido) + Red de Agencieros + Posible entrega — pedido de
    Daniel 15/09/2026 (continuación 18, ampliado en continuación 26): que
    buscar no dependa de estar parado en una pestaña puntual, y que tenga en
    cuenta la máxima cantidad de fuentes posibles. Devuelve una lista de
    dicts ya normalizados (mismas claves para un vehículo propio, una
    publicación de la Red o un vehículo de permuta) y ordenados por origen
    según ORDEN_ORIGEN: Disponible, Por ingresar, En reparación, Red · Ofrece,
    Posible entrega, Red · Busca.

    Multi-tenant (18/09/2026): Stock y "Posible entrega" (pedidos propios)
    se filtran por `agencia_id` -- son datos propios. Red de Agencieros a
    propósito NO se filtra: es la cartelera compartida entre todas las
    agencias, se busca igual que se ve en /red/."""
    # Import acá adentro (no al tope del módulo) para evitar un import
    # circular: database.py no depende de este módulo, pero varias rutas
    # importan buscador antes que database en el arranque de la app.
    from flask import url_for
    from database import query, foto_principal

    cond_stock, params_stock = condiciones_sql(filtros, campo_precio="valor_publicado", campo_km="km")
    cond_stock.append("estado IN ('disponible','por_ingresar','en_reparacion')")
    cond_stock.append("agencia_id = ?")
    params_stock.append(agencia_id)
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

    posibles_entregas = _buscar_posible_entrega(filtros, agencia_id)
    posibles_senas = _buscar_posible_entrega_senas(filtros, agencia_id)
    posibles_planes = _buscar_posible_entrega_planes(filtros, agencia_id)

    por_origen = {clave: [] for clave in ORDEN_ORIGEN}
    for v in vehiculos:
        por_origen[v["estado"]].append({
            "origen": v["estado"],
            "id": v["id"],
            "marca": v["marca"], "modelo": v["modelo"], "version": v["version"],
            "anio": v["anio"], "km": v["km"], "precio": v["valor_publicado"],
            "ver_url": url_for("stock.detalle", vehiculo_id=v["id"]),
            "agencia": None, "contacto": None,
            "foto": foto_principal(v["id"]),
        })
    for p in publicaciones:
        origen = "red_ofrece" if p["tipo"] == "ofrezco" else "red_busca"
        por_origen[origen].append({
            "origen": origen,
            "marca": p["marca"], "modelo": p["modelo"], "version": p["version"],
            "anio": p["anio"], "km": p["km"], "precio": p["precio"],
            "ver_url": None,
            "agencia": p["agencia_nombre"], "contacto": p["contacto"],
            # La Red todavía no tiene fotos propias — sin foto de muestra
            # acá para no insinuar que es una foto real de otra agencia.
            "foto": None,
        })
    for pe in posibles_entregas:
        por_origen["posible_entrega"].append({
            "origen": "posible_entrega",
            "marca": pe["permuta_marca"], "modelo": pe["permuta_modelo"], "version": pe["permuta_version"],
            "anio": pe["permuta_anio"], "km": pe["permuta_km"],
            # Todavía no tiene precio de venta asignado (es un vehículo que
            # el cliente ofrece, no algo que la agencia ya está publicando).
            "precio": None,
            "ver_url": url_for("pedidos.detalle", pedido_id=pe["id"]),
            "agencia": pe["cliente_nombre"], "contacto": pe["telefono"],
            "foto": None,
        })

    for vt in posibles_senas:
        por_origen["posible_entrega"].append({
            "origen": "posible_entrega",
            "marca": vt["permuta_marca"], "modelo": vt["permuta_modelo"], "version": vt["permuta_version"],
            "anio": vt["permuta_anio"], "km": vt["permuta_km"],
            "precio": None,
            # Seña abierta: a la ficha del vehículo señado (ahí está la operación).
            # Venta ya cerrada: a la pantalla donde se decide el destino de la permuta.
            "ver_url": (url_for("stock.permuta_destino", origen="venta", item_id=vt["id"])
                        if vt["estado"] == "cerrada" else url_for("stock.detalle", vehiculo_id=vt["vehiculo_id"])),
            "agencia": vt["cliente_nombre"], "contacto": vt["cliente_telefono"],
            "foto": None,
        })

    for fp in posibles_planes:
        por_origen["posible_entrega"].append({
            "origen": "posible_entrega",
            "marca": fp["permuta_marca"], "modelo": fp["permuta_modelo"], "version": fp["permuta_version"],
            "anio": fp["permuta_anio"], "km": fp["permuta_km"],
            "precio": None,
            # Plan en trámite: al plan (ahí está la operación). Operación ya cerrada:
            # a la pantalla donde se decide el destino de la permuta.
            "ver_url": (url_for("stock.permuta_destino", origen="plan", item_id=fp["id"])
                        if fp["estado"] != "pendiente_firma" else url_for("financiacion.detalle", financiacion_id=fp["id"])),
            "agencia": fp["cliente_nombre"] or "Financiación en trámite", "contacto": fp["cliente_telefono"],
            "foto": None,
        })

    resultados = []
    for clave in ORDEN_ORIGEN:
        for item in por_origen[clave]:
            item["origen_label"] = ORIGEN_LABEL[clave]
            item["origen_badge"] = ORIGEN_BADGE[clave]
            resultados.append(item)
    return resultados
