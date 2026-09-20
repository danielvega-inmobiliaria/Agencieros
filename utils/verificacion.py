"""Validación de mail al registrar una agencia nueva (Red de Agencieros
multi-tenant, 18/09/2026).

Mismo patrón que ya usa APP_PRESUPUESTOPRO (utils/verificacion.py ahí):
código numérico de 6 dígitos, vence en 15 minutos, se manda por Resend.

Sin RESEND_API_KEY configurada en el entorno, no rompe nada: el código
queda igual guardado en la base (así se puede seguir probando el flujo
completo en local) y se imprime en la consola del servidor en vez de
mandarse por mail de verdad -- hay que cargar esa variable de entorno
antes de invitar a una agencia amiga de verdad a registrarse.
"""
import os
import secrets
from datetime import datetime, timedelta

from database import get_db

CODIGO_EXPIRA_MIN = 15


def generar_codigo():
    """Código de 6 dígitos generado con `secrets` (no random) porque se usa
    para autenticar -- mismo criterio que cualquier token de sesión."""
    return f"{secrets.randbelow(1_000_000):06d}"


def crear_codigo(agencia_id):
    """Invalida códigos anteriores sin usar de esa agencia y crea uno
    nuevo. Devuelve el código en texto plano (se manda una sola vez, no se
    vuelve a leer de la base)."""
    codigo = generar_codigo()
    expira = (datetime.utcnow() + timedelta(minutes=CODIGO_EXPIRA_MIN)).isoformat()
    db = get_db()
    db.execute(
        "UPDATE verificacion_codigos SET usado = 1 WHERE agencia_id = ? AND usado = 0",
        (agencia_id,),
    )
    db.execute(
        "INSERT INTO verificacion_codigos (agencia_id, codigo, expira_at) VALUES (?, ?, ?)",
        (agencia_id, codigo, expira),
    )
    db.commit()
    return codigo


def validar_codigo(agencia_id, codigo_ingresado):
    """True/False. Si es correcto y no venció, lo marca usado y marca la
    agencia como con mail verificado."""
    db = get_db()
    fila = db.execute(
        """SELECT id, expira_at FROM verificacion_codigos
           WHERE agencia_id = ? AND codigo = ? AND usado = 0
           ORDER BY id DESC LIMIT 1""",
        (agencia_id, (codigo_ingresado or "").strip()),
    ).fetchone()
    if not fila:
        return False
    try:
        vencido = datetime.utcnow() > datetime.fromisoformat(fila["expira_at"])
    except ValueError:
        vencido = True
    if vencido:
        return False
    db.execute("UPDATE verificacion_codigos SET usado = 1 WHERE id = ?", (fila["id"],))
    db.execute("UPDATE agencias SET email_verificado = 1 WHERE id = ?", (agencia_id,))
    db.commit()
    return True


def enviar_codigo_email(email, nombre_agencia, codigo):
    """Manda el código por Resend. Devuelve True si lo mandó de verdad,
    False si solo quedó en el log del servidor (sin RESEND_API_KEY todavía,
    o si falló el envío -- en ambos casos el código ya está guardado en la
    base y se puede seguir probando el flujo a mano)."""
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        print(f"[verificacion] Sin RESEND_API_KEY -- código para {email}: {codigo}")
        return False
    try:
        import resend

        resend.api_key = api_key
        remitente = os.environ.get("RESEND_FROM", "Agencieros <noreply@agencieros.net.ar>")
        resend.Emails.send(
            {
                "from": remitente,
                "to": [email],
                "subject": f"Tu código de verificación: {codigo}",
                "html": (
                    '<div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;'
                    'padding:24px;color:#222">'
                    '<h2 style="color:#0d1e3c">Confirmá tu cuenta en AGENCIEROS</h2>'
                    f"<p>Hola,</p>"
                    f"<p>Tu código para validar el registro de <strong>{nombre_agencia}</strong> es:</p>"
                    f'<div style="text-align:center;margin:28px 0">'
                    f'<span style="font-size:32px;font-weight:bold;letter-spacing:6px;'
                    f'color:#0d1e3c">{codigo}</span></div>'
                    f"<p style=\"color:#888;font-size:.85rem\">Vence en {CODIGO_EXPIRA_MIN} minutos. "
                    "Si no lo pediste vos, ignorá este mensaje.</p>"
                    "</div>"
                ),
            }
        )
        return True
    except Exception as e:
        print(f"[verificacion] Error enviando email a {email}: {e} -- código: {codigo}")
        return False
