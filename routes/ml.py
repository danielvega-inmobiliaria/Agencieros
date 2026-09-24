"""Conexión con MercadoLibre (24/09/2026) -- ver mercado_ml.py.

/ml/            estado de la conexión + búsqueda de prueba (solo agencia 1)
/ml/conectar    manda a MercadoLibre a autorizar la app (Authorization Code)
/ml/callback    vuelve de MercadoLibre con el código (redirect registrado en
                developers.mercadolibre.com.ar: https://app.agencieros.net.ar/ml/callback)
/ml/desconectar borra el token de usuario guardado
"""

import secrets

from flask import Blueprint, render_template, request, redirect, url_for, flash, session

import mercado_ml
from database import execute

bp = Blueprint("ml", __name__, url_prefix="/ml")


class _NoEsPlataforma(Exception):
    pass


def _solo_plataforma():
    # La cuenta de ML es una sola para toda la plataforma (la usan todas las
    # agencias para el rango de mercado): la conecta/administra la agencia 1.
    if session.get("agencia_id") != 1:
        raise _NoEsPlataforma()


@bp.errorhandler(_NoEsPlataforma)
def _aviso_no_plataforma(e):
    # En vez del "Forbidden" pelado (24/09/2026): decir con qué agencia está
    # abierta la sesión, que es casi siempre el motivo.
    flash(
        f"La conexión con MercadoLibre la administra solo Italia Automotores. Ahora estás con la sesión de "
        f"\"{session.get('agencia_nombre') or 'otra agencia'}\" -- salí y volvé a entrar con la cuenta de Italia Automotores.",
        "error",
    )
    return redirect(url_for("admin.index"))


@bp.route("/")
def estado():
    _solo_plataforma()
    prueba = None
    if request.args.get("probar") and mercado_ml.disponible():
        prueba = mercado_ml.rango_mercado("Toyota", "Etios", "", request.args.get("anio") or "2018")
    return render_template("ml/estado.html", estado=mercado_ml.estado_conexion(), prueba=prueba,
                           redirect_uri=mercado_ml.redirect_uri())


@bp.route("/conectar")
def conectar():
    _solo_plataforma()
    if not mercado_ml.disponible():
        flash("Faltan ML_CLIENT_ID / ML_CLIENT_SECRET en las variables de Railway.", "error")
        return redirect(url_for("ml.estado"))
    state = secrets.token_urlsafe(16)
    session["ml_state"] = state
    return redirect(mercado_ml.url_autorizacion(state))


@bp.route("/callback")
def callback():
    _solo_plataforma()
    if request.args.get("error"):
        flash(f"MercadoLibre no autorizó la conexión: {request.args.get('error_description') or request.args.get('error')}", "error")
        return redirect(url_for("ml.estado"))
    if not request.args.get("state") or request.args.get("state") != session.pop("ml_state", None):
        flash("La respuesta de MercadoLibre no coincide con el pedido (state). Probá conectar de nuevo.", "error")
        return redirect(url_for("ml.estado"))
    ok, msg = mercado_ml.canjear_codigo(request.args.get("code", ""))
    if ok:
        execute("DELETE FROM ml_cache")  # que las próximas búsquedas usen el token nuevo
    flash(msg, "success" if ok else "error")
    return redirect(url_for("ml.estado"))


@bp.route("/desconectar", methods=["POST"])
def desconectar():
    _solo_plataforma()
    execute("DELETE FROM ml_tokens")
    flash("Cuenta de MercadoLibre desconectada.", "success")
    return redirect(url_for("ml.estado"))
