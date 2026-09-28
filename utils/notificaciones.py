"""Avisos al administrador de AGENCIEROS (28/09/2026): mail + push.

- Mail: por Resend (misma cuenta que los códigos de verificación), a
  ADMIN_EMAIL (default danve61@gmail.com).
- Push al celular: por ntfy (https://ntfy.sh, app gratis para iPhone y
  Android). Se instala la app, se suscribe al tema que esté en la variable
  NTFY_TOPIC y listo: cada aviso llega como notificación. El tema funciona
  como contraseña, por eso tiene que ser largo y difícil de adivinar.

Nunca frena la acción del usuario: si falta configuración o falla el envío,
solo queda anotado en el log.
"""
import json
import os
import urllib.request

APP_URL = os.environ.get("APP_URL", "https://app.agencieros.net.ar").rstrip("/")


def _mail(asunto, texto, responder_a=None):
    api_key = os.environ.get("RESEND_API_KEY")
    destino = os.environ.get("ADMIN_EMAIL", "danve61@gmail.com")
    if not api_key:
        print(f"[notificaciones] Sin RESEND_API_KEY -- {asunto}: {texto}")
        return False
    try:
        import resend
        resend.api_key = api_key
        payload = {
            "from": os.environ.get("RESEND_FROM", "Agencieros <noreply@agencieros.net.ar>"),
            "to": [destino],
            "subject": asunto,
            "text": texto,
        }
        if responder_a:
            payload["reply_to"] = [responder_a]
        resend.Emails.send(payload)
        return True
    except Exception as e:
        print(f"[notificaciones] Error enviando mail: {e}")
        return False


def _push(titulo, texto, url=None):
    tema = os.environ.get("NTFY_TOPIC", "").strip()
    if not tema:
        return False
    servidor = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    cuerpo = {"topic": tema, "title": titulo, "message": texto[:1000], "tags": ["car"]}
    if url:
        cuerpo["click"] = url
    try:
        req = urllib.request.Request(
            servidor, data=json.dumps(cuerpo).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        urllib.request.urlopen(req, timeout=5).read()
        return True
    except Exception as e:
        print(f"[notificaciones] Error enviando push: {e}")
        return False


def notificar_admin(asunto, texto, ruta=None, responder_a=None):
    """Manda el aviso por mail y push. `ruta` (ej. "/plataforma/mensajes")
    se agrega como link al mail y se abre al tocar la notificación."""
    url = APP_URL + ruta if ruta else None
    texto_mail = texto + (f"\n\nVer en la app:\n{url}" if url else "")
    _mail(asunto, texto_mail, responder_a)
    _push(asunto, texto, url)
