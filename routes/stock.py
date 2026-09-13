from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import query, execute
from sync_stock import sync_stock

bp = Blueprint("stock", __name__, url_prefix="/stock")

ESTADOS = ["disponible", "por_ingresar", "en_reparacion", "vendido"]
ESTADO_LABEL = {
    "disponible": "Disponible",
    "por_ingresar": "Por ingresar",
    "en_reparacion": "En reparación",
    "vendido": "Vendido",
}


def _rentabilidad(v):
    costo = (v["valor_compra"] or 0) + (v["gastos"] or 0)
    referencia = v["valor_vendido"] if v["estado"] == "vendido" and v["valor_vendido"] else v["valor_publicado"]
    ganancia_bruta = (referencia or 0) - costo
    rentabilidad_pct = (ganancia_bruta / costo * 100) if costo else 0
    dias = None
    if v["fecha_ingreso"]:
        fin = v["fecha_venta"] or str(date.today())
        try:
            d1 = date.fromisoformat(v["fecha_ingreso"][:10])
            d2 = date.fromisoformat(fin[:10])
            dias = (d2 - d1).days
        except ValueError:
            dias = None
    return {
        "costo_total": costo,
        "ganancia_bruta": ganancia_bruta,
        "rentabilidad_pct": rentabilidad_pct,
        "dias_en_stock": dias,
    }


@bp.route("/sincronizar", methods=["POST"])
def sincronizar():
    resultado = sync_stock()
    if resultado["error"]:
        flash(f"No se pudo sincronizar con STOCK: {resultado['error']}", "error")
    else:
        partes = []
        if resultado["nuevos"]:
            partes.append(f"{len(resultado['nuevos'])} vehículo(s) nuevo(s)")
        if resultado["actualizados"]:
            partes.append(f"{len(resultado['actualizados'])} actualizado(s)")
        if not partes:
            partes.append("sin cambios")
        mensaje = "Sincronización con STOCK: " + ", ".join(partes) + "."
        if resultado["sin_ficha"]:
            mensaje += f" Carpetas sin ficha (ignoradas): {', '.join(resultado['sin_ficha'])}."
        flash(mensaje, "success")
    return redirect(url_for("stock.index"))


@bp.route("/")
def index():
    estado_filtro = request.args.get("estado", "todos")
    if estado_filtro in ESTADOS:
        vehiculos = query("SELECT * FROM vehiculos WHERE estado = ? ORDER BY created_at DESC", (estado_filtro,))
    else:
        vehiculos = query("SELECT * FROM vehiculos ORDER BY created_at DESC")
    conteos = {r["estado"]: r["c"] for r in query("SELECT estado, COUNT(*) c FROM vehiculos GROUP BY estado")}
    return render_template(
        "stock/index.html",
        vehiculos=vehiculos,
        estado_filtro=estado_filtro,
        estados=ESTADOS,
        estado_label=ESTADO_LABEL,
        conteos=conteos,
    )


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    prefill = {
        "marca": request.args.get("marca", ""),
        "modelo": request.args.get("modelo", ""),
        "version": request.args.get("version", ""),
        "anio": request.args.get("anio", ""),
        "valor_publicado": request.args.get("precio_referencia", ""),
    }
    if request.method == "POST":
        f = request.form
        vehiculo_id = execute(
            """INSERT INTO vehiculos
               (marca, modelo, version, anio, km, combustible, caja, color, dominio, estado,
                equipamiento, observaciones, documentacion, valor_compra, gastos, valor_publicado,
                fecha_ingreso)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                f.get("marca"), f.get("modelo"), f.get("version"), f.get("anio") or None,
                f.get("km") or None, f.get("combustible"), f.get("caja"), f.get("color"),
                f.get("dominio"), f.get("estado", "disponible"), f.get("equipamiento"),
                f.get("observaciones"), f.get("documentacion"),
                float(f.get("valor_compra") or 0), float(f.get("gastos") or 0),
                float(f.get("valor_publicado") or 0), str(date.today()),
            ),
        )

        # Módulo 3: aviso automático si hay un pedido de cliente que matchea.
        matches = query(
            """SELECT * FROM pedidos_clientes
               WHERE estado = 'buscando' AND marca = ? AND modelo = ?
                 AND (anio_desde IS NULL OR ? >= anio_desde)
                 AND (anio_hasta IS NULL OR ? <= anio_hasta)""",
            (f.get("marca"), f.get("modelo"), f.get("anio") or 0, f.get("anio") or 9999),
        )
        if matches:
            nombres = ", ".join(m["cliente_nombre"] for m in matches)
            flash(f"⚡ Este vehículo matchea con {len(matches)} pedido(s) del Banco de pedidos: {nombres}", "success")
        else:
            flash("Vehículo cargado en stock.", "success")
        return redirect(url_for("stock.detalle", vehiculo_id=vehiculo_id))

    return render_template("stock/form.html", vehiculo=None, prefill=prefill, estados=ESTADOS, estado_label=ESTADO_LABEL)


@bp.route("/<int:vehiculo_id>")
def detalle(vehiculo_id):
    vehiculo = query("SELECT * FROM vehiculos WHERE id = ?", (vehiculo_id,), one=True)
    if not vehiculo:
        flash("Vehículo no encontrado.", "error")
        return redirect(url_for("stock.index"))
    return render_template("stock/detalle.html", vehiculo=vehiculo, rent=_rentabilidad(vehiculo), estado_label=ESTADO_LABEL)


@bp.route("/<int:vehiculo_id>/editar", methods=["GET", "POST"])
def editar(vehiculo_id):
    vehiculo = query("SELECT * FROM vehiculos WHERE id = ?", (vehiculo_id,), one=True)
    if not vehiculo:
        flash("Vehículo no encontrado.", "error")
        return redirect(url_for("stock.index"))

    if request.method == "POST":
        f = request.form
        fecha_venta = str(date.today()) if f.get("estado") == "vendido" and vehiculo["estado"] != "vendido" else vehiculo["fecha_venta"]
        execute(
            """UPDATE vehiculos SET marca=?, modelo=?, version=?, anio=?, km=?, combustible=?, caja=?,
               color=?, dominio=?, estado=?, equipamiento=?, observaciones=?, documentacion=?,
               valor_compra=?, gastos=?, valor_publicado=?, valor_vendido=?, fecha_venta=?,
               updated_at=datetime('now')
               WHERE id=?""",
            (
                f.get("marca"), f.get("modelo"), f.get("version"), f.get("anio") or None,
                f.get("km") or None, f.get("combustible"), f.get("caja"), f.get("color"),
                f.get("dominio"), f.get("estado"), f.get("equipamiento"), f.get("observaciones"),
                f.get("documentacion"), float(f.get("valor_compra") or 0), float(f.get("gastos") or 0),
                float(f.get("valor_publicado") or 0),
                float(f.get("valor_vendido")) if f.get("valor_vendido") else None,
                fecha_venta, vehiculo_id,
            ),
        )
        flash("Vehículo actualizado.", "success")
        return redirect(url_for("stock.detalle", vehiculo_id=vehiculo_id))

    return render_template("stock/form.html", vehiculo=vehiculo, prefill=None, estados=ESTADOS, estado_label=ESTADO_LABEL)
