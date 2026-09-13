from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import query, execute

bp = Blueprint("pedidos", __name__, url_prefix="/pedidos")


@bp.route("/")
def index():
    estado_filtro = request.args.get("estado", "buscando")
    if estado_filtro == "todos":
        pedidos = query("SELECT * FROM pedidos_clientes ORDER BY created_at DESC")
    else:
        pedidos = query(
            "SELECT * FROM pedidos_clientes WHERE estado = ? ORDER BY created_at DESC", (estado_filtro,)
        )
    return render_template("pedidos/index.html", pedidos=pedidos, estado_filtro=estado_filtro)


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        f = request.form
        execute(
            """INSERT INTO pedidos_clientes
               (cliente_nombre, telefono, marca, modelo, version, anio_desde, anio_hasta,
                precio_maximo, forma_pago, observaciones)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                f.get("cliente_nombre"), f.get("telefono"), f.get("marca"), f.get("modelo"),
                f.get("version"), f.get("anio_desde") or None, f.get("anio_hasta") or None,
                float(f.get("precio_maximo") or 0) or None, f.get("forma_pago"), f.get("observaciones"),
            ),
        )
        flash("Pedido guardado. Te avisamos automáticamente si ingresa un vehículo que matchea.", "success")
        return redirect(url_for("pedidos.index"))
    return render_template("pedidos/form.html")


@bp.route("/<int:pedido_id>/resolver")
def resolver(pedido_id):
    execute("UPDATE pedidos_clientes SET estado = 'resuelto' WHERE id = ?", (pedido_id,))
    flash("Pedido marcado como resuelto.", "success")
    return redirect(url_for("pedidos.index"))


@bp.route("/<int:pedido_id>/cancelar")
def cancelar(pedido_id):
    execute("UPDATE pedidos_clientes SET estado = 'cancelado' WHERE id = ?", (pedido_id,))
    flash("Pedido cancelado.", "success")
    return redirect(url_for("pedidos.index"))
