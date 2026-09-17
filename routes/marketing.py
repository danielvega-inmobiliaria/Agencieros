from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import query, execute
from parser_informe_marketing import parsear

bp = Blueprint("marketing", __name__, url_prefix="/marketing")


@bp.route("/")
def index():
    """Lista de vehículos de Stock (no vendidos) con el estado de su
    contenido de Marketing -- pedido de Daniel 17/09/2026: un lugar central
    para ver a qué vehículos les falta cargar el informe/textos de venta."""
    vehiculos = query(
        """SELECT v.id, v.marca, v.modelo, v.version, v.anio, v.estado,
                  m.updated_at AS marketing_actualizado
           FROM vehiculos v
           LEFT JOIN marketing_vehiculo m ON m.vehiculo_id = v.id
           WHERE v.estado != 'vendido'
           ORDER BY (m.id IS NOT NULL), v.created_at DESC"""
    )
    return render_template("marketing/index.html", vehiculos=vehiculos)


@bp.route("/<int:vehiculo_id>", methods=["GET", "POST"])
def detalle(vehiculo_id):
    vehiculo = query("SELECT * FROM vehiculos WHERE id = ?", (vehiculo_id,), one=True)
    if not vehiculo:
        flash("Vehículo no encontrado.", "error")
        return redirect(url_for("marketing.index"))

    contenido = query(
        "SELECT * FROM marketing_vehiculo WHERE vehiculo_id = ?", (vehiculo_id,), one=True
    )

    if request.method == "POST":
        texto = request.form.get("contenido_markdown", "")
        if contenido:
            execute(
                "UPDATE marketing_vehiculo SET contenido_markdown = ?, updated_at = datetime('now') WHERE vehiculo_id = ?",
                (texto, vehiculo_id),
            )
        else:
            execute(
                "INSERT INTO marketing_vehiculo (vehiculo_id, contenido_markdown) VALUES (?, ?)",
                (vehiculo_id, texto),
            )
        flash("Contenido de Marketing guardado.", "success")
        return redirect(url_for("marketing.detalle", vehiculo_id=vehiculo_id))

    parseado = parsear(contenido["contenido_markdown"]) if contenido and contenido["contenido_markdown"] else None

    return render_template(
        "marketing/detalle.html",
        vehiculo=vehiculo,
        contenido=contenido,
        parseado=parseado,
    )
