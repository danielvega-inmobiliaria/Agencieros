from flask import Blueprint, render_template, request, jsonify

from database import query

bp = Blueprint("precios", __name__, url_prefix="/precios")


@bp.route("/")
def index():
    marcas = [r["marca"] for r in query("SELECT DISTINCT marca FROM precios_base ORDER BY marca")]
    return render_template("precios/index.html", marcas=marcas)


@bp.route("/api/modelos")
def api_modelos():
    marca = request.args.get("marca", "")
    rows = query(
        "SELECT DISTINCT modelo FROM precios_base WHERE marca = ? ORDER BY modelo", (marca,)
    )
    return jsonify([r["modelo"] for r in rows])


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
