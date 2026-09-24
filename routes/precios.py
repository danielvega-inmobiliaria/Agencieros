from flask import Blueprint, render_template, request, jsonify

from database import query
from comparables import links_comparables

bp = Blueprint("precios", __name__, url_prefix="/precios")


@bp.route("/")
def index():
    # La búsqueda arranca por Año: mostramos el universo completo de años
    # cargados para el datalist inicial (ver charla 13-14/09/2026 — antes
    # arrancaba por Marca, ahora Marca/Modelo/Versión se acotan solos una
    # vez elegido el Año).
    anios = [r["anio"] for r in query("SELECT DISTINCT anio FROM precios_base ORDER BY anio DESC")]
    return render_template("precios/index.html", anios=anios)



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
        """SELECT marca, modelo, version, precio_referencia, fuente FROM precios_base
           WHERE anio = ? ORDER BY UPPER(marca), modelo, version""",
        (anio,),
    )
    return jsonify([
        {
            "label": etiqueta_vehiculo(r["marca"], r["modelo"], r["version"]),
            "marca": r["marca"], "modelo": r["modelo"], "version": r["version"],
            "precio": r["precio_referencia"], "fuente": r["fuente"],
        }
        for r in rows
    ])


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
    )
