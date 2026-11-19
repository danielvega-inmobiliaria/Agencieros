"""Avisos al administrador de AGENCIEROS (28/09/2026): mail + push.

- Mail: por Resend (misma cuenta que los códigos de verificación), a
  ADMIN_EMAIL (default danve61@gmail.com).
- Telegram (opcional, 19/11/2026): bot propio; TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID.
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


def _mail(asunto, texto, responder_a=None, destino=None):
    api_key = os.environ.get("RESEND_API_KEY")
    destino = destino or os.environ.get("ADMIN_EMAIL", "danve61@gmail.com")
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
    # 19/11/2026: prioridad 1-5 (NTFY_PRIORITY, default 4 = alta) para que el iPhone lo muestre como alerta.
    try:
        cuerpo["priority"] = min(5, max(1, int(os.environ.get("NTFY_PRIORITY", "4"))))
    except ValueError:
        cuerpo["priority"] = 4
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


def _telegram(titulo, texto, url=None):
    """Aviso por Telegram (19/11/2026): el bot le escribe a un chat del admin,
    donde se puede poner un sonido propio. Variables: TELEGRAM_BOT_TOKEN (de
    @BotFather) y TELEGRAM_CHAT_ID. Si falta alguna, no hace nada."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        return False
    cuerpo = f"{titulo}\n\n{texto}" + (f"\n\n{url}" if url else "")
    try:
        datos = json.dumps({"chat_id": chat, "text": cuerpo[:4000], "disable_web_page_preview": True}).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=datos,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        urllib.request.urlopen(req, timeout=5).read()
        return True
    except Exception as e:
        # No se imprime la URL (lleva el token): solo el tipo de error.
        print(f"[notificaciones] Error enviando Telegram: {type(e).__name__}", flush=True)
        return False


def notificar_admin(asunto, texto, ruta=None, responder_a=None):
    """Manda el aviso por mail y push. `ruta` (ej. "/plataforma/mensajes")
    se agrega como link al mail y se abre al tocar la notificación."""
    url = APP_URL + ruta if ruta else None
    texto_mail = texto + (f"\n\nVer en la app:\n{url}" if url else "")
    _mail(asunto, texto_mail, responder_a)
    _push(asunto, texto, url)
    _telegram(asunto, texto, url)


def avisar_agencia(email, asunto, texto, ruta=None):
    """Mail a una agencia (ej. la respuesta del admin a su consulta)."""
    if not email:
        return False
    url = APP_URL + ruta if ruta else None
    return _mail(asunto, texto + (f"\n\nVer en la app:\n{url}" if url else ""), destino=email,
                 responder_a=os.environ.get("ADMIN_EMAIL", "danve61@gmail.com"))
