from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import query, execute

bp = Blueprint("tomas", __name__, url_prefix="/tomas")

PUNTOS = [
    ("motor", "Motor"), ("caja", "Caja"), ("embrague", "Embrague"), ("frenos", "Frenos"),
    ("suspension", "Suspensión"), ("direccion", "Dirección"), ("interior", "Interior"),
    ("tapizados", "Tapizados"), ("cubiertas", "Cubiertas"), ("electricidad", "Electricidad"),
    ("aire_acondicionado", "Aire acondicionado"), ("documentacion", "Documentación"),
]
CALIFICACIONES = ["Excelente", "Bueno", "Regular", "Malo"]


@bp.route("/")
def index():
    tomas = query("SELECT * FROM tomas_vehiculo ORDER BY created_at DESC")
    return render_template("tomas/index.html", tomas=tomas)


@bp.route("/nueva", methods=["GET", "POST"])
def nueva():
    prefill = {
        "marca": request.args.get("marca", ""),
        "modelo": request.args.get("modelo", ""),
        "version": request.args.get("version", ""),
        "anio": request.args.get("anio", ""),
    }
    if request.method == "POST":
        f = request.form
        toma_id = execute(
            """INSERT INTO tomas_vehiculo
               (marca, modelo, version, anio, evaluador, motor, caja, embrague, frenos, suspension,
                direccion, interior, tapizados, cubiertas, electricidad, aire_acondicionado,
                documentacion, observaciones)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                f.get("marca"), f.get("modelo"), f.get("version"), f.get("anio") or None,
                f.get("evaluador"),
                f.get("motor"), f.get("caja"), f.get("embrague"), f.get("frenos"), f.get("suspension"),
                f.get("direccion"), f.get("interior"), f.get("tapizados"), f.get("cubiertas"),
                f.get("electricidad"), f.get("aire_acondicionado"), f.get("documentacion"),
                f.get("observaciones"),
            ),
        )
        flash("Toma de vehículo registrada.", "success")
        return redirect(url_for("tomas.detalle", toma_id=toma_id))
    return render_template("tomas/form.html", puntos=PUNTOS, calificaciones=CALIFICACIONES, prefill=prefill)


@bp.route("/<int:toma_id>")
def detalle(toma_id):
    toma = query("SELECT * FROM tomas_vehiculo WHERE id = ?", (toma_id,), one=True)
    if not toma:
        flash("Toma no encontrada.", "error")
        return redirect(url_for("tomas.index"))
    return render_template("tomas/detalle.html", toma=toma, puntos=PUNTOS)
