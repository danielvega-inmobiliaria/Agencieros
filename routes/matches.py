"""Pantalla "Matches": botón/página dedicada que corre la búsqueda cruzada
sobre toda la base (pedidos activos entre sí + Stock + Red) y devuelve un
solo listado con todos los matches vigentes — para revisarlos de una sola
vez, sin depender de entrar pedido por pedido y sin que un match se pase por
alto (pedido de Daniel 15/09/2026, continuación 27: "otra que pienso es
tener un botón de Match que haga la búsqueda entrecruzada de la base y tire
un listado de Matcheo").

Reutiliza exactamente la misma lógica que ya corre al cargar/abrir un
pedido (`_buscar_oferta_para_pedido` y `_buscar_matches_permuta` en
routes/pedidos.py) — este módulo no duplica ningún criterio de búsqueda,
solo la recorre para todos los pedidos activos de una vez."""

from flask import Blueprint, render_template, session

from database import query
from routes.pedidos import _buscar_oferta_para_pedido, _buscar_matches_permuta, _con_fecha_y_dias

bp = Blueprint("matches", __name__, url_prefix="/matches")


def _matches_por_pedido():
    """Corre el cruce completo para cada pedido activo ('buscando') de la
    agencia actual y devuelve solo los que tienen al menos un match --
    reutilizado tanto por la pantalla de Matches como por el contador del
    menú, para no tener dos lugares con el mismo criterio.

    Filtra por agencia_id (18/09/2026, junto con el escalado de Pedidos a
    multi-tenant) para no mezclar pedidos de otra agencia en el cruce de
    Daniel -- Matches en sí sigue bloqueado para cualquier otra agencia
    (MODULOS_SOLO_AGENCIA_1 en app.py), esto es solo para no filtrar datos
    ajenos el día que haya una 2da agencia real con pedidos cargados."""
    agencia_id = session["agencia_id"]
    pedidos = query(
        "SELECT * FROM pedidos_clientes WHERE agencia_id = ? AND estado = 'buscando' ORDER BY created_at DESC",
        (agencia_id,),
    )
    filas = []
    for p_raw in pedidos:
        p = _con_fecha_y_dias(p_raw)
        ofertas = _buscar_oferta_para_pedido(
            p.get("marca"), p.get("modelo"), p.get("anio_desde"), p.get("precio_maximo")
        )
        matches_propios, matches_red = [], []
        if p.get("forma_pago") == "permuta" and p.get("permuta_marca"):
            matches_propios, matches_red = _buscar_matches_permuta(
                agencia_id, p["permuta_marca"], p.get("permuta_modelo"), excluir_pedido_id=p["id"]
            )
        if ofertas or matches_propios or matches_red:
            filas.append({
                "pedido": p,
                "ofertas": ofertas,
                "matches_propios": matches_propios,
                "matches_red": matches_red,
            })
    return filas


def contar_matches():
    """Cuántos pedidos activos tienen al menos un match pendiente de
    revisar — usado para el badge del menú (ver app.py), así se ve desde
    cualquier pantalla que hay algo nuevo sin tener que entrar a Matches."""
    return len(_matches_por_pedido())


@bp.route("/")
def index():
    return render_template("matches/index.html", filas=_matches_por_pedido())
