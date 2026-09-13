"""Bandeja unificada de mensajes — VISTA PREVIA / SIMULACIÓN.

Este módulo todavía no está conectado a WhatsApp, Instagram, Facebook ni
Email reales. Las conversaciones de abajo son datos de ejemplo hardcodeados,
pensados solo para que se pueda ver y sentir cómo quedaría la bandeja
unificada una vez que se integre mensajería real (ver PROYECTO.md, sección
IDEAS FUTURAS).
"""

from flask import Blueprint, render_template, request

bp = Blueprint("mensajes", __name__, url_prefix="/mensajes")

CANAL_LABEL = {
    "whatsapp": "WhatsApp",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "email": "Email",
}

CANAL_ICONO = {
    "whatsapp": "💬",
    "instagram": "📷",
    "facebook": "👍",
    "email": "✉️",
}

CONVERSACIONES = [
    {
        "id": 1,
        "canal": "whatsapp",
        "contacto": "Martín Ibáñez",
        "detalle_contacto": "+54 9 341 555-0123",
        "ultimo_mensaje": "Y hacen algo por una Amarok 2017 en parte de pago?",
        "hora": "14:32",
        "no_leidos": 2,
        "mensajes": [
            {"de": "cliente", "texto": "Hola, buenas tardes", "hora": "14:20"},
            {"de": "cliente", "texto": "Vi la Hilux 4x4 2021 que publicaron, ¿sigue disponible?", "hora": "14:21"},
            {"de": "agencia", "texto": "¡Hola Martín! Sí, sigue disponible. ¿Querés coordinar para verla?", "hora": "14:25"},
            {"de": "cliente", "texto": "Dale, ¿puede ser mañana a la tarde?", "hora": "14:31"},
            {"de": "cliente", "texto": "Y hacen algo por una Amarok 2017 en parte de pago?", "hora": "14:32"},
        ],
    },
    {
        "id": 2,
        "canal": "instagram",
        "contacto": "@valentina.ruiz",
        "detalle_contacto": "Instagram Direct",
        "ultimo_mensaje": "Vi la story del Corolla, ¿cuánto sale?",
        "hora": "13:10",
        "no_leidos": 0,
        "mensajes": [
            {"de": "cliente", "texto": "Vi la story del Corolla, ¿cuánto sale?", "hora": "13:10"},
        ],
    },
    {
        "id": 3,
        "canal": "facebook",
        "contacto": "Jorge Paredes",
        "detalle_contacto": "Facebook Messenger",
        "ultimo_mensaje": "Buenas, ¿hacen permuta por una Ranger?",
        "hora": "Ayer 18:45",
        "no_leidos": 1,
        "mensajes": [
            {"de": "cliente", "texto": "Buenas, ¿hacen permuta por una Ranger?", "hora": "Ayer 18:45"},
        ],
    },
    {
        "id": 4,
        "canal": "email",
        "contacto": "Transportes Norte SRL",
        "detalle_contacto": "contacto@transportesnorte.com",
        "ultimo_mensaje": "Consulta por flota de utilitarios",
        "hora": "Ayer 09:20",
        "no_leidos": 0,
        "mensajes": [
            {
                "de": "cliente",
                "texto": "Buen día, estamos evaluando renovar 4 utilitarios. ¿Tienen stock de Partner/Kangoo?",
                "hora": "Ayer 09:20",
            },
        ],
    },
    {
        "id": 5,
        "canal": "whatsapp",
        "contacto": "Lucía Fernández",
        "detalle_contacto": "+54 9 341 555-0456",
        "ultimo_mensaje": "Gracias! Paso mañana a verlo",
        "hora": "Lun",
        "no_leidos": 0,
        "mensajes": [
            {"de": "agencia", "texto": "Te confirmo turno para mañana 10hs, ¿te queda bien?", "hora": "Lun 16:02"},
            {"de": "cliente", "texto": "Gracias! Paso mañana a verlo", "hora": "Lun 16:05"},
        ],
    },
    {
        "id": 6,
        "canal": "instagram",
        "contacto": "@rodrigo.motors",
        "detalle_contacto": "Instagram Direct",
        "ultimo_mensaje": "¿Tienen algo similar en gris?",
        "hora": "Lun",
        "no_leidos": 0,
        "mensajes": [
            {"de": "cliente", "texto": "¿Tienen algo similar en gris?", "hora": "Lun 11:40"},
        ],
    },
]


def _por_id(conv_id):
    for c in CONVERSACIONES:
        if c["id"] == conv_id:
            return c
    return None


def contar_no_leidos():
    """Total de mensajes sin leer (para el indicador del Dashboard)."""
    return sum(c["no_leidos"] for c in CONVERSACIONES)


@bp.route("/")
def index():
    conv_id = request.args.get("id", type=int)
    seleccionada = _por_id(conv_id) if conv_id else None
    if seleccionada is None:
        seleccionada = CONVERSACIONES[0]
    return render_template(
        "mensajes/index.html",
        conversaciones=CONVERSACIONES,
        seleccionada=seleccionada,
        canal_label=CANAL_LABEL,
        canal_icono=CANAL_ICONO,
    )
