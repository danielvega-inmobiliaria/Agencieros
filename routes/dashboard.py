from flask import Blueprint, render_template

from database import query
from routes.mensajes import contar_no_leidos

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@bp.route("/")
def index():
    stock_counts = {
        row["estado"]: row["c"]
        for row in query("SELECT estado, COUNT(*) c FROM vehiculos GROUP BY estado")
    }
    pedidos_activos = query(
        "SELECT COUNT(*) c FROM pedidos_clientes WHERE estado = 'buscando'", one=True
    )["c"]
    ventas_mes = query(
        """SELECT COUNT(*) c, COALESCE(SUM(valor_vendido - valor_compra - gastos), 0) ganancia
           FROM vehiculos
           WHERE estado = 'vendido' AND strftime('%Y-%m', fecha_venta) = strftime('%Y-%m', 'now')""",
        one=True,
    )
    ultimos_vehiculos = query(
        "SELECT * FROM vehiculos ORDER BY created_at DESC LIMIT 5"
    )
    # Indicador de mensajes sin leer (bandeja unificada — vista previa con datos de ejemplo).
    mensajes_no_leidos = contar_no_leidos()
    return render_template(
        "dashboard.html",
        stock_counts=stock_counts,
        pedidos_activos=pedidos_activos,
        ventas_mes=ventas_mes,
        ultimos_vehiculos=ultimos_vehiculos,
        mensajes_no_leidos=mensajes_no_leidos,
    )
