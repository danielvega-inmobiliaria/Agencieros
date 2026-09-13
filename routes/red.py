from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import query, execute

bp = Blueprint("red", __name__, url_prefix="/red")


@bp.route("/")
def index():
    tipo_filtro = request.args.get("tipo", "todos")
    if tipo_filtro in ("ofrezco", "busco"):
        publicaciones = query(
            "SELECT * FROM red_publicaciones WHERE tipo = ? AND estado = 'activo' ORDER BY created_at DESC",
            (tipo_filtro,),
        )
    else:
        publicaciones = query(
            "SELECT * FROM red_publicaciones WHERE estado = 'activo' ORDER BY created_at DESC"
        )
    return render_template("red/index.html", publicaciones=publicaciones, tipo_filtro=tipo_filtro)


@bp.route("/nueva", methods=["GET", "POST"])
def nueva():
    if request.method == "POST":
        f = request.form
        execute(
            """INSERT INTO red_publicaciones
               (agencia_nombre, tipo, marca, modelo, version, anio, precio, descripcion, contacto)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                f.get("agencia_nombre"), f.get("tipo"), f.get("marca"), f.get("modelo"),
                f.get("version"), f.get("anio") or None, float(f.get("precio") or 0) or None,
                f.get("descripcion"), f.get("contacto"),
            ),
        )
        flash("Publicación creada en la Red de Agencieros.", "success")
        return redirect(url_for("red.index"))
    return render_template("red/form.html")


@bp.route("/<int:pub_id>/cerrar")
def cerrar(pub_id):
    execute("UPDATE red_publicaciones SET estado = 'cerrado' WHERE id = ?", (pub_id,))
    flash("Publicación cerrada.", "success")
    return redirect(url_for("red.index"))
