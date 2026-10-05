from flask import Blueprint, render_template, request, jsonify, session

from database import query, execute
from comparables import links_comparables
import mercado_ml

bp = Blueprint("precios", __name__, url_prefix="/precios")


@bp.route("/")
def index():
    # La búsqueda arranca por Año: mostramos el universo completo de años
    # cargados para el datalist inicial (ver charla 13-14/09/2026 — antes
    # arrancaba por Marca, ahora Marca/Modelo/Versión se acotan solos una
    # vez elegido el Año).
    anios = [r["anio"] for r in query("SELECT DISTINCT anio FROM precios_base ORDER BY anio DESC")]
    return render_template("precios/index.html", anios=anios)



_MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
          "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12}


def etiqueta_referencia(fuente, fecha_actualizacion=None):
    """Texto que ve el usuario al lado del precio (24/09/2026): sin nombrar
    la fuente -- no hay acuerdo con ningún proveedor de guías de precios --,
    solo el mes del dato: "Valor de referencia · actualizado 09/2026".
    El mes sale del nombre interno de la fuente ("... Sep-2026"); si no lo
    tiene, de la fecha de carga (AAAA-MM-DD)."""
    import re
    m = re.search(r"([A-Za-z]{3})-(\d{4})", fuente or "")
    if m and m.group(1).lower() in _MESES:
        return f"Valor de referencia · actualizado {_MESES[m.group(1).lower()]:02d}/{m.group(2)}"
    f = str(fecha_actualizacion or "")
    if re.match(r"\d{4}-\d{2}", f):
        return f"Valor de referencia · actualizado {f[5:7]}/{f[:4]}"
    return "Valor de referencia"


def etiqueta_vehiculo(marca, modelo, version):
    """Texto de cada opción del buscador, igual que lo muestra Decreditos
    (conectado a InfoAuto): "TOYOTA - ETIOS 1.5 4 PTAS PLATINUM"."""
    return f"{(marca or '').upper()} - {' '.join(p for p in [modelo, version] if p)}".strip()


@bp.route("/api/opciones")
def api_opciones():
    """Buscador estilo Decreditos (24/09/2026, pedido de Daniel): elegido el
    Año, un solo campo "Marca / Modelo" con todas las versiones que tienen
    precio ESE año, en una sola línea (marca - modelo versión) y con el
    valor ya incluido para mostrarlo apenas se elige, sin otra consulta."""
    anio = request.args.get("anio", "")
    if not anio:
        return jsonify([])
    rows = query(
        """SELECT marca, modelo, version, precio_referencia, fuente, fecha_actualizacion FROM precios_base
           WHERE anio = ? ORDER BY UPPER(marca), modelo, version""",
        (anio,),
    )
    return jsonify([
        {
            "label": etiqueta_vehiculo(r["marca"], r["modelo"], r["version"]),
            "marca": r["marca"], "modelo": r["modelo"], "version": r["version"],
            "precio": r["precio_referencia"],
            "etiqueta": etiqueta_referencia(r["fuente"], r["fecha_actualizacion"]),
        }
        for r in rows
    ])


def registrar_consulta(marca, modelo, version, anio, encontrado=True):
    """Anota la consulta para el contador del Panel de Agencias (28/09/2026).
    No cuenta al admin de la plataforma, y si la misma agencia vuelve a ver
    el mismo vehículo dentro de los 10 minutos (ej. al volver con "atrás"
    desde RosarioGarage) no se cuenta de nuevo."""
    agencia_id = session.get("agencia_id")
    if not agencia_id:
        return
    try:
        repetida = query(
            """SELECT 1 FROM consultas_precios
               WHERE agencia_id = ? AND COALESCE(marca,'') = ? AND COALESCE(modelo,'') = ?
                 AND COALESCE(version,'') = ? AND COALESCE(anio,'') = ?
                 AND created_at >= datetime('now', '-10 minutes')""",
            (agencia_id, marca or "", modelo or "", version or "", str(anio or "")),
            one=True,
        )
        if not repetida:
            execute(
                """INSERT INTO consultas_precios (agencia_id, anio, marca, modelo, version, encontrado)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (agencia_id, str(anio or ""), marca, modelo, version, 1 if encontrado else 0),
            )
    except Exception:
        pass


@bp.route("/api/comparables")
def api_comparables():
    """Links de comparables (MercadoLibre/RosarioGarage/Facebook) para el
    vehículo elegido en el buscador, sin salir de la pantalla (24/09/2026).
    Se llama una vez por cada versión elegida: ahí se cuenta la consulta."""
    a = request.args
    registrar_consulta(a.get("marca", ""), a.get("modelo", ""), a.get("version", ""), a.get("anio", ""))
    return jsonify(links_comparables(a.get("marca", ""), a.get("modelo", ""), a.get("version", ""), a.get("anio", "")))


@bp.route("/api/mercado")
def api_mercado():
    """Rango de precios de mercado de MercadoLibre (API oficial, cache 24 h)
    para el vehículo elegido -- ver mercado_ml.py. Sin credenciales de ML
    devuelve {"disponible": false} y la pantalla no muestra nada."""
    a = request.args
    return jsonify(mercado_ml.rango_mercado(a.get("marca", ""), a.get("modelo", ""),
                                            a.get("version", ""), a.get("anio", "")))


@bp.route("/api/publicaciones")
def api_publicaciones():
    """3 publicaciones reales en pesos de RosarioGarage (28/09/2026) -- ver
    publicaciones_rg.py. Se usa cuando MercadoLibre no da datos."""
    import publicaciones_rg
    a = request.args
    return jsonify(publicaciones_rg.publicaciones(a.get("marca", ""), a.get("modelo", ""), a.get("version", ""),
                                                  a.get("anio", ""), a.get("valor_tabla")))


def _zona_habilitada():
    """Prueba de 'publicaciones por zona' (05/10/2026): solo la agencia 1 (Italia)."""
    import os
    return session.get("agencia_id") == int(os.environ.get("STOCK_SYNC_AGENCIA_ID", "1"))


def _zona_origen(a):
    """(texto de localidad, es_por_defecto) -- la de la agencia si no se eligió."""
    from database import obtener_config_agencia
    origen = (a.get("localidad") or "").strip()
    if origen:
        return origen, False
    cfg = obtener_config_agencia(session.get("agencia_id")) or {}
    return ", ".join(x for x in (cfg.get("ciudad"), cfg.get("provincia")) if x), True


def _zona_params(a):
    import zona_deautos
    modo = "radio" if a.get("modo") == "radio" else "region"
    region = a.get("region") or "Centro"
    if region != "todo" and region not in zona_deautos.REGIONES:
        region = "Centro"
    try:
        radio = int(a.get("radio") or 100)
    except ValueError:
        radio = 100
    return modo, region, max(5, min(radio, 1500))


@bp.route("/api/zona")
def api_zona():
    """Avisos de DeAutos por región o por radio (km) de una localidad -- ver
    zona_deautos.py. Prueba solo para la agencia 1."""
    if not _zona_habilitada():
        return jsonify({"habilitado": False}), 403
    import os
    import zona_deautos
    a = request.args
    origen, por_defecto = _zona_origen(a)
    modo, region, radio = _zona_params(a)
    res = zona_deautos.buscar(a.get("marca", ""), a.get("modelo", ""), a.get("version", ""), a.get("anio", ""),
                              modo, region, origen, radio, query, execute, fuente=a.get("fuente") or None)
    if os.environ.get("AUTOCOSMOS_ACTIVO", "1") != "1":
        res["ac_pedidos"] = []
    res.update({"habilitado": True, "localidad_texto": origen, "por_defecto": por_defecto,
                "radios": zona_deautos.RADIOS})
    return jsonify(res)


@bp.route("/api/zona_autocosmos")
def api_zona_autocosmos():
    """Una provincia de Autocosmos (prueba solo agencia 1; sus términos piden
    autorización escrita, pedida el 05/10/2026: se apaga con AUTOCOSMOS_ACTIVO=0)."""
    if not _zona_habilitada():
        return jsonify({"habilitado": False}), 403
    import os
    import zona_deautos
    if os.environ.get("AUTOCOSMOS_ACTIVO", "1") != "1":
        return jsonify({"habilitado": True, "ok": False, "avisos": [], "motivo": "Autocosmos desactivado."})
    a = request.args
    origen, _ = _zona_origen(a)
    modo, region, radio = _zona_params(a)
    try:
        cod = int(a.get("cod") or 0)
    except ValueError:
        cod = 0
    res = zona_deautos.autocosmos(a.get("marca", ""), a.get("modelo", ""), a.get("version", ""), a.get("anio", ""),
                                  cod, modo, region, origen, radio, query, execute)
    res["habilitado"] = True
    return jsonify(res)


@bp.route("/api/localidades")
def api_localidades():
    if not _zona_habilitada():
        return jsonify({"localidades": [], "regiones": []}), 403
    import zona_deautos
    return jsonify({"localidades": zona_deautos.nombres_localidades(), "regiones": zona_deautos.nombres_regiones()})


@bp.route("/api/marcas")
def api_marcas():
    """Marcas para el datalist. Con Año ya elegido, solo las marcas que
    tienen algún precio cargado para ese año — así no se ofrecen marcas
    que en ese año no tienen ninguna versión con precio."""
    anio = request.args.get("anio", "")
    if anio:
        rows = query("SELECT DISTINCT marca FROM precios_base WHERE anio = ? ORDER BY marca", (anio,))
    else:
        rows = query("SELECT DISTINCT marca FROM precios_base ORDER BY marca")
    return jsonify([r["marca"] for r in rows])


@bp.route("/api/modelos")
def api_modelos():
    """Modelos para el datalist de autocompletar, acotados por Marca y/o
    Año (los que ya estén elegidos). Sin marca —búsqueda directa por
    modelo— devuelve el universo (filtrado por año si corresponde)."""
    marca = request.args.get("marca", "")
    anio = request.args.get("anio", "")
    sql = "SELECT DISTINCT modelo FROM precios_base WHERE 1=1"
    params = []
    if marca:
        sql += " AND marca = ?"
        params.append(marca)
    if anio:
        sql += " AND anio = ?"
        params.append(anio)
    sql += " ORDER BY modelo"
    rows = query(sql, tuple(params))
    return jsonify([r["modelo"] for r in rows])


@bp.route("/api/marcas_por_modelo")
def api_marcas_por_modelo():
    """Cuando se busca directo por modelo sin elegir marca antes: dice qué
    marca(s) tienen ese modelo (acotado también por Año, si ya está
    elegido), para autocompletarla sola si es una única marca, o mostrar
    un selector chico con solo esas opciones si el modelo existe en más
    de una marca."""
    modelo = request.args.get("modelo", "")
    anio = request.args.get("anio", "")
    sql = "SELECT DISTINCT marca FROM precios_base WHERE modelo = ?"
    params = [modelo]
    if anio:
        sql += " AND anio = ?"
        params.append(anio)
    sql += " ORDER BY marca"
    rows = query(sql, tuple(params))
    return jsonify([r["marca"] for r in rows])


@bp.route("/api/versiones")
def api_versiones():
    """Versiones para Marca+Modelo. Con Año elegido, solo las que
    realmente tienen precio cargado para ese año puntual — el resto no
    se muestra (pedido explícito: no mezclar versiones de otros años)."""
    marca = request.args.get("marca", "")
    modelo = request.args.get("modelo", "")
    anio = request.args.get("anio", "")
    sql = "SELECT DISTINCT version FROM precios_base WHERE marca = ? AND modelo = ?"
    params = [marca, modelo]
    if anio:
        sql += " AND anio = ?"
        params.append(anio)
    sql += " ORDER BY version"
    rows = query(sql, tuple(params))
    return jsonify([r["version"] for r in rows])


@bp.route("/api/anios")
def api_anios():
    """Años disponibles para una Marca+Modelo+Versión puntual. Resguardo
    para cuando se llega a elegir la Versión sin haber puesto el Año
    primero (el flujo recomendado es Año primero, pero no es
    obligatorio): si hay un solo año posible se completa solo, si hay
    varios se le pregunta al agenciero cuál."""
    marca = request.args.get("marca", "")
    modelo = request.args.get("modelo", "")
    version = request.args.get("version", "")
    rows = query(
        """SELECT DISTINCT anio FROM precios_base
           WHERE marca = ? AND modelo = ? AND version = ? ORDER BY anio DESC""",
        (marca, modelo, version),
    )
    return jsonify([r["anio"] for r in rows])


@bp.route("/buscar")
def buscar():
    marca = request.args.get("marca", "")
    modelo = request.args.get("modelo", "")
    version = request.args.get("version", "")
    anio = request.args.get("anio", "")
    # Texto libre del buscador cuando el vehículo no está en la lista (no
    # hay Marca/Modelo/Versión separados): se usa tal cual como "modelo"
    # para los links de comparables y para precargar Toma/Stock.
    texto_libre = request.args.get("q", "").strip()
    if texto_libre and not (marca or modelo):
        modelo = texto_libre
        # "Buscar igual": vehículo que no está en la lista (también cuenta).
        registrar_consulta("", texto_libre, "", anio, encontrado=False)

    resultado = query(
        """SELECT * FROM precios_base
           WHERE marca = ? AND modelo = ? AND version = ? AND anio = ?""",
        (marca, modelo, version, anio),
        one=True,
    )
    historial = query(
        """SELECT anio, precio_referencia FROM precios_base
           WHERE marca = ? AND modelo = ? AND version = ? ORDER BY anio""",
        (marca, modelo, version),
    )
    # Mientras el listado de InfoAuto no está resuelto, un vehículo que no
    # aparece en precios_base se queda sin ningún valor de referencia -- se
    # ofrecen los mismos links de búsqueda directa (MercadoLibre,
    # RosarioGarage, Facebook Marketplace) que ya se usan en la Tasación de
    # la Toma, para que el agenciero pueda cotejar precios reales a ojo
    # (pedido de Daniel 22/09/2026).
    links_comparables_busqueda = None if resultado else links_comparables(marca, modelo, version, anio)
    return render_template(
        "precios/resultado.html",
        resultado=resultado,
        historial=historial,
        marca=marca,
        modelo=modelo,
        version=version,
        anio=anio,
        links_comparables=links_comparables_busqueda,
        etiqueta_ref=etiqueta_referencia(resultado["fuente"], resultado["fecha_actualizacion"]) if resultado else None,
    )
