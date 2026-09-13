from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import query, execute

bp = Blueprint("pedidos", __name__, url_prefix="/pedidos")

FORMAS_PAGO = ["contado", "cuotas", "permuta"]
FORMA_PAGO_LABEL = {
    "contado": "Contado",
    "cuotas": "Cuotas",
    "permuta": "Permuta",
}


def _buscar_matches_permuta(marca, modelo, excluir_pedido_id=None):
    """Cruza el vehículo que el cliente ofrece en permuta contra:
    - otros pedidos propios (clientes buscando ese mismo marca/modelo), y
    - la Red de Agencieros (publicaciones tipo 'busco' de otras agencias).
    Así el agenciero ve de una si ese auto de permuta ya tiene comprador."""
    if not marca:
        return [], []

    cond_propios = "estado = 'buscando' AND LOWER(marca) = LOWER(?)"
    params_propios = [marca]
    if excluir_pedido_id:
        cond_propios += " AND id != ?"
        params_propios.append(excluir_pedido_id)
    if modelo:
        cond_propios += " AND LOWER(modelo) = LOWER(?)"
        params_propios.append(modelo)
    propios = query(
        f"SELECT * FROM pedidos_clientes WHERE {cond_propios} ORDER BY created_at DESC",
        tuple(params_propios),
    )

    cond_red = "tipo = 'busco' AND estado = 'activo' AND LOWER(marca) = LOWER(?)"
    params_red = [marca]
    if modelo:
        cond_red += " AND LOWER(modelo) = LOWER(?)"
        params_red.append(modelo)
    red = query(
        f"SELECT * FROM red_publicaciones WHERE {cond_red} ORDER BY created_at DESC",
        tuple(params_red),
    )

    return propios, red


def _con_fecha_y_dias(pedido):
    """Convierte un Row de pedidos_clientes en dict, agregando fecha en
    formato DD/MM/YYYY y los días transcurridos desde que se cargó —
    para poder evaluar de un vistazo cuánto tiempo lleva cada pedido."""
    d = dict(pedido)
    d["fecha_str"] = "-"
    d["dias_transcurridos"] = None
    if d.get("created_at"):
        try:
            fecha = date.fromisoformat(d["created_at"][:10])
            d["fecha_str"] = fecha.strftime("%d/%m/%Y")
            d["dias_transcurridos"] = (date.today() - fecha).days
        except ValueError:
            pass
    return d


@bp.route("/")
def index():
    estado_filtro = request.args.get("estado", "buscando")
    if estado_filtro == "todos":
        pedidos_raw = query("SELECT * FROM pedidos_clientes ORDER BY created_at DESC")
    else:
        pedidos_raw = query(
            "SELECT * FROM pedidos_clientes WHERE estado = ? ORDER BY created_at DESC", (estado_filtro,)
        )
    pedidos = [_con_fecha_y_dias(p) for p in pedidos_raw]
    return render_template(
        "pedidos/index.html",
        pedidos=pedidos,
        estado_filtro=estado_filtro,
        forma_pago_label=FORMA_PAGO_LABEL,
    )


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        f = request.form
        forma_pago = f.get("forma_pago", "contado")
        con_financiacion = forma_pago in ("cuotas", "permuta")
        es_permuta = forma_pago == "permuta"

        pedido_id = execute(
            """INSERT INTO pedidos_clientes
               (cliente_nombre, telefono, marca, modelo, version, anio_desde, anio_hasta,
                precio_maximo, forma_pago, observaciones,
                efectivo_disponible, cuota_maxima,
                permuta_marca, permuta_modelo, permuta_version, permuta_anio, permuta_km,
                permuta_combustible, permuta_caja, permuta_color, permuta_observaciones)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                f.get("cliente_nombre"), f.get("telefono"), f.get("marca"), f.get("modelo"),
                f.get("version"), f.get("anio_desde") or None, f.get("anio_hasta") or None,
                float(f.get("precio_maximo") or 0) or None, forma_pago, f.get("observaciones"),
                float(f.get("efectivo_disponible") or 0) if con_financiacion and f.get("efectivo_disponible") else None,
                float(f.get("cuota_maxima") or 0) if con_financiacion and f.get("cuota_maxima") else None,
                f.get("permuta_marca") if es_permuta else None,
                f.get("permuta_modelo") if es_permuta else None,
                f.get("permuta_version") if es_permuta else None,
                (f.get("permuta_anio") or None) if es_permuta else None,
                (f.get("permuta_km") or None) if es_permuta else None,
                f.get("permuta_combustible") if es_permuta else None,
                f.get("permuta_caja") if es_permuta else None,
                f.get("permuta_color") if es_permuta else None,
                f.get("permuta_observaciones") if es_permuta else None,
            ),
        )

        mensaje = "Pedido guardado. Te avisamos automáticamente si ingresa un vehículo que matchea."
        if es_permuta and f.get("permuta_marca"):
            propios, red = _buscar_matches_permuta(
                f.get("permuta_marca"), f.get("permuta_modelo"), excluir_pedido_id=pedido_id
            )
            if propios or red:
                partes = []
                if propios:
                    nombres = ", ".join(p["cliente_nombre"] for p in propios)
                    partes.append(f"{len(propios)} pedido(s) propio(s) buscando ese vehículo ({nombres})")
                if red:
                    agencias = ", ".join(r["agencia_nombre"] for r in red)
                    partes.append(f"{len(red)} publicación(es) de la Red buscando ese vehículo ({agencias})")
                mensaje = "⚡ El vehículo de permuta matchea con " + " y ".join(partes) + "."
            else:
                mensaje = "Pedido guardado. El vehículo de permuta no matchea con nadie por ahora."

        flash(mensaje, "success")
        return redirect(url_for("pedidos.index"))
    return render_template("pedidos/form.html", formas_pago=FORMAS_PAGO, forma_pago_label=FORMA_PAGO_LABEL)


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
