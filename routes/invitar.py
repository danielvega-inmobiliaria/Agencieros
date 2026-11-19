"""«Invitar a un colega» (19/11/2026): link con código, botón de WhatsApp y
seguimiento de los colegas invitados. Solo el dueño de la agencia."""
from datetime import datetime
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
    invitados = []
    for r in referidos.lista_de(agencia_id):
        d = dict(r)
        d["dias_sin_entrar"] = _dias_desde(d["ultima_actividad"])
        tel = "".join(ch for ch in (d["telefono"] or "") if ch.isdigit())
        if tel:
            msg = (f"Hola! Soy de una agencia que usa AGENCIEROS. Vi que te registraste con mi link: "
                   f"si necesitás una mano para cargar tus autos y armar la red entre agencieros, avisame.")
            d["wa"] = f"https://wa.me/{tel if tel.startswith('54') else '54' + tel}?text=" + quote(msg)
        else:
            d["wa"] = ""
        invitados.append(d)
    resumen = {
        "total": len(invitados),
        "validaron": sum(1 for i in invitados if i["email_verificado"]),
        "con_autos": sum(1 for i in invitados if i["autos_stock"]),
        "contrataron": sum(1 for i in invitados if i["pago_at"]),
    }
    return render_template(
        "cuenta/invitar.html", link=link, codigo=codigo,
        wa_url="https://wa.me/?text=" + quote(texto),
        invitados=invitados, resumen=resumen,
        meses=referidos.meses_acreditados(agencia_id),
    )


def _dias_desde(ts):
    """Días desde una fecha guardada por SQLite (UTC); None si nunca entró."""
    if not ts:
        return None
    try:
        return max(0, (datetime.utcnow() - datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")).days)
    except ValueError:
        return None
