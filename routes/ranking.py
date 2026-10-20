"""Ranking de vendedores (20/10/2026). Solo para el dueño de la agencia.

Sin columnas nuevas: sale de vehiculos.vendido_por_id / senado_por_id,
ventas.fecha_sena, financiaciones y agencia_usuarios. Todo filtrado por
agencia_id. Lo vendido sin vendedor asignado (datos anteriores al multiusuario)
va a "Sin asignar".

Definiciones (se muestran en pantalla):
- Vendidas: unidades en estado vendido cuya fecha de venta cae en el período.
- Señas tomadas: unidades con senado_por_id = vendedor, fechadas por la seña
  (ventas.fecha_sena; si no hay, la financiación; si no, la fecha de venta).
- Señas que terminaron en venta: de esas, las que hoy están vendidas.
  Conversión = vendidas / (vendidas + perdidas); las que siguen señadas
  (en trámite) no cuentan ni a favor ni en contra.
- Financiadas: vendidas con un plan de financiación no cancelado.
- Ganancia = valor vendido − (compra + gastos).
"""
from datetime import date, timedelta

from flask import Blueprint, render_template, session, redirect, url_for, flash, request

from database import query
from utils.permisos import es_dueno
from utils.sucursales import contexto_selector, filtro_sql

bp = Blueprint("ranking", __name__, url_prefix="/ranking")

PERIODOS = [("mes", "Este mes"), ("mes_ant", "Mes anterior"), ("90", "Últimos 90 días"), ("total", "Total")]


def rango_periodo(clave, hoy=None):
    """(desde, hasta) como 'YYYY-MM-DD' inclusivos; None = sin límite."""
    hoy = hoy or date.today()
    if clave == "mes_ant":
        fin = hoy.replace(day=1) - timedelta(days=1)
        return fin.replace(day=1).isoformat(), fin.isoformat()
    if clave == "90":
        return (hoy - timedelta(days=90)).isoformat(), hoy.isoformat()
    if clave == "total":
        return None, None
    return hoy.replace(day=1).isoformat(), hoy.isoformat()


def _en(fecha, desde, hasta):
    if desde is None:
        return True
    f = (fecha or "")[:10]
    return bool(f) and desde <= f <= hasta


def calcular(agencia_id, clave="mes", hoy=None):
    """Devuelve dict con filas (ordenadas por unidades) y totales."""
    desde, hasta = rango_periodo(clave, hoy)
    suc_sql, suc_par = filtro_sql("v.sucursal_id")
    vehs = query(
        f"""SELECT v.id, v.estado, v.vendido_por_id, v.senado_por_id, v.fecha_venta,
                   v.valor_vendido, v.valor_compra, v.gastos,
                   (SELECT MAX(fecha_sena) FROM ventas x WHERE x.vehiculo_id = v.id AND x.agencia_id = v.agencia_id) AS f_sena,
                   (SELECT MAX(created_at) FROM financiaciones f WHERE f.vehiculo_id = v.id AND f.agencia_id = v.agencia_id) AS f_fin,
                   (SELECT COUNT(*) FROM financiaciones f WHERE f.vehiculo_id = v.id AND f.agencia_id = v.agencia_id
                       AND f.estado NOT IN ('cancelado', 'cancelado_reserva')) AS n_fin
            FROM vehiculos v
            WHERE v.agencia_id = ? AND (v.estado = 'vendido' OR v.senado_por_id IS NOT NULL){suc_sql}""",
        [agencia_id] + suc_par,
    )
    usuarios = {u["id"]: u for u in query(
        "SELECT id, nombre, rol, activo FROM agencia_usuarios WHERE agencia_id = ?", (agencia_id,))}

    filas = {}

    def fila(uid):
        # Un id que no es de esta agencia se trata como sin asignar.
        if uid not in usuarios:
            uid = None
        if uid not in filas:
            u = usuarios.get(uid)
            filas[uid] = {
                "uid": uid, "nombre": u["nombre"] if u else "Sin asignar",
                "rol": u["rol"] if u else None, "activo": bool(u["activo"]) if u else True,
                "unidades": 0, "monto": 0.0, "ganancia": 0.0, "financiadas": 0,
                "senas": 0, "senas_vendidas": 0, "senas_perdidas": 0, "senas_tramite": 0,
            }
        return filas[uid]

    for v in vehs:
        if v["estado"] == "vendido" and _en(v["fecha_venta"], desde, hasta):
            f = fila(v["vendido_por_id"])
            f["unidades"] += 1
            vv = v["valor_vendido"] or 0
            f["monto"] += vv
            f["ganancia"] += vv - (v["valor_compra"] or 0) - (v["gastos"] or 0)
            if v["n_fin"]:
                f["financiadas"] += 1
        if v["senado_por_id"] is not None:
            fecha_sena = v["f_sena"] or v["f_fin"] or (v["fecha_venta"] if v["estado"] == "vendido" else None)
            if _en(fecha_sena, desde, hasta):
                f = fila(v["senado_por_id"])
                f["senas"] += 1
                if v["estado"] == "vendido":
                    f["senas_vendidas"] += 1
                elif v["estado"] == "senado":
                    f["senas_tramite"] += 1
                else:
                    f["senas_perdidas"] += 1

    # Usuarios activos sin movimiento en el período: aparecen con 0.
    for uid, u in usuarios.items():
        if u["activo"]:
            fila(uid)
    lista = list(filas.values())
    for f in lista:
        cerradas = f["senas_vendidas"] + f["senas_perdidas"]
        f["conversion"] = round(100 * f["senas_vendidas"] / cerradas) if cerradas else None
        f["sin_asignar"] = f["uid"] is None
    # Orden: unidades, luego monto; "Sin asignar" siempre al final.
    lista.sort(key=lambda f: (f["sin_asignar"], -f["unidades"], -f["monto"], f["nombre"].lower()))
    maximo = max([f["unidades"] for f in lista] + [1])
    for f in lista:
        f["barra"] = round(100 * f["unidades"] / maximo)
    con_ventas = [f for f in lista if f["unidades"] > 0 and not f["sin_asignar"]]
    mejor = con_ventas[0] if con_ventas else None
    return {
        "filas": lista, "mejor": mejor, "desde": desde, "hasta": hasta,
        "total_unidades": sum(f["unidades"] for f in lista),
        "total_monto": sum(f["monto"] for f in lista),
        "total_ganancia": sum(f["ganancia"] for f in lista),
    }


def top3(agencia_id, clave="mes"):
    r = calcular(agencia_id, clave)
    return [f for f in r["filas"] if f["unidades"] > 0 and not f["sin_asignar"]][:3]


@bp.route("/")
def index():
    if not es_dueno():
        flash("Esa sección es solo para el dueño de la agencia.", "error")
        return redirect(url_for("precios.index"))
    clave = request.args.get("p", "mes")
    if clave not in dict(PERIODOS):
        clave = "mes"
    selector = contexto_selector()
    r = calcular(session["agencia_id"], clave)
    return render_template(
        "ranking/index.html", **selector, suc_endpoint="ranking.index", suc_args={"p": clave},
        periodos=PERIODOS, periodo=clave, periodo_nombre=dict(PERIODOS)[clave], r=r,
    )
