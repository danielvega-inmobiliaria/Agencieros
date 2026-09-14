from flask import Blueprint, render_template, request, jsonify

from database import query

bp = Blueprint("precios", __name__, url_prefix="/precios")


@bp.route("/")
def index():
    marcas = [r["marca"] for r in query("SELECT DISTINCT marca FROM precios_base ORDER BY marca")]
    return render_template("precios/index.html", marcas=marcas)


@bp.route("/api/modelos")
def api_modelos():
    """Modelos para el datalist de autocompletar. Con marca elegida, solo
    los de esa marca (como antes). Sin marca —búsqueda directa por
    modelo, sin pasar primero por el desplegable de marcas— devuelve el
    universo completo para que el campo Modelo funcione solo."""
    marca = request.args.get("marca", "")
    if marca:
        rows = query(
            "SELECT DISTINCT modelo FROM precios_base WHERE marca = ? ORDER BY modelo", (marca,)
        )
    else:
        rows = query("SELECT DISTINCT modelo FROM precios_base ORDER BY modelo")
    return jsonify([r["modelo"] for r in rows])


@bp.route("/api/marcas_por_modelo")
def api_marcas_por_modelo():
    """Cuando se busca directo por modelo sin elegir marca antes: dice qué
    marca(s) tienen ese modelo, para autocompletarla sola si es una única
    marca, o mostrar un selector chico con solo esas opciones (nunca el
    desplegable completo) si el modelo existe en más de una marca."""
    modelo = request.args.get("modelo", "")
    rows = query(
        "SELECT DISTINCT marca FROM precios_base WHERE modelo = ? ORDER BY marca", (modelo,)
    )
    return jsonify([r["marca"] for r in rows])


@bp.route("/api/versiones")
def api_versiones():
    marca = request.args.get("marca", "")
    modelo = request.args.get("modelo", "")
    rows = query(
        "SELECT DISTINCT version FROM precios_base WHERE marca = ? AND modelo = ? ORDER BY version",
        (marca, modelo),
    )
    return jsonify([r["version"] for r in rows])


@bp.route("/api/anios")
def api_anios():
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
    return render_template(
        "precios/resultado.html",
        resultado=resultado,
        historial=historial,
        marca=marca,
        modelo=modelo,
        version=version,
        anio=anio,
    )
