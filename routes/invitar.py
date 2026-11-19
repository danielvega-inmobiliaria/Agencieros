"""«Invitar a un colega» (19/11/2026): link con código, botón de WhatsApp y
seguimiento de los colegas invitados. Solo el dueño de la agencia."""
from urllib.parse import quote

from flask import Blueprint, render_template, request, session, url_for

from utils import referidos

bp = Blueprint("invitar", __name__, url_prefix="/invitar")


def _link(codigo):
    url = url_for("auth.registro", ref=codigo, _external=True)
    if url.startswith("http://") and "localhost" not in url and "127.0.0.1" not in url:
        url = "https://" + url[len("http://"):]
    return url


@bp.route("/")
def index():
    agencia_id = session["agencia_id"]
    codigo = referidos.codigo_de(agencia_id)
    link = _link(codigo) if codigo else ""
    texto = ("Te invito a probar AGENCIEROS, la app para agencias de autos (precios, stock, tasación y "
             f"una red entre agencieros). Registrate gratis desde mi link: {link}")
    return render_template(
        "cuenta/invitar.html", link=link, codigo=codigo,
        wa_url="https://wa.me/?text=" + quote(texto),
        invitados=referidos.lista_de(agencia_id),
        meses=referidos.meses_acreditados(agencia_id),
        tope=referidos.MAX_MESES_CREDITO,
    )
