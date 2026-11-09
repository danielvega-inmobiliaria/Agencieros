"""Defensa contra bots en el registro y en los mails con código (09/11/2026).

Problema: bots se registraban con mails ajenos y con spam en el nombre de la
agencia («4000$ BONUS CODE»); cada registro mandaba un código por Resend a la
víctima y agotaba la cuota diaria. Capas, de más barata a más fuerte:

1. Trampas: campo oculto (honeypot) y tiempo mínimo entre abrir y enviar el
   formulario (lo maneja routes/auth.py con `trampa_*`).
2. Cloudflare Turnstile (`verificar_turnstile`): desafío invisible/liviano.
   Variables de entorno: TURNSTILE_SITE_KEY y TURNSTILE_SECRET_KEY. Si falta
   la secreta, no se exige (queda un aviso en el log) para no trabar el
   registro mientras se configura.
3. Límites por IP, por mail y un tope global de mails por hora/día
   (`autorizar_envio`), guardados en SQLite (tabla antibot_eventos), así
   sobreviven reinicios y sirven con varios workers de gunicorn.
4. Validación del nombre de agencia y de los textos libres
   (`validar_nombre_agencia`, `validar_texto_libre`).

Topes configurables por variable de entorno (opcionales):
ANTIBOT_MAX_MAILS_HORA (25) y ANTIBOT_MAX_MAILS_DIA (60). Resend gratis
permite 100 mails por día: el tope diario deja margen para el resto.
"""
import json
import os
import re
import unicodedata
import urllib.parse
import urllib.request

from flask import request

from database import execute, query

TURNSTILE_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# Segundos mínimos entre que se abre el formulario y se envía (un humano
# tarda mucho más en completar 8 campos).
TIEMPO_MINIMO_FORM = 4


# --- IP ---------------------------------------------------------------------
def ip_cliente():
    """IP del visitante detrás del proxy de Railway. Se prefiere X-Real-IP
    (la fija el proxy), después la ÚLTIMA entrada de X-Forwarded-For (la que
    agrega el proxy más cercano; la primera la puede inventar el cliente) y
    por último la dirección directa."""
    ip = (request.headers.get("X-Real-IP") or "").strip()
    if not ip:
        xff = request.headers.get("X-Forwarded-For", "")
        partes = [p.strip() for p in xff.split(",") if p.strip()]
        ip = partes[-1] if partes else ""
    if not ip:
        ip = request.remote_addr or "?"
    return ip[:45]


# --- Límites ----------------------------------------------------------------
def _asegurar_tabla():
    execute(
        """CREATE TABLE IF NOT EXISTS antibot_eventos (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               tipo TEXT NOT NULL,
               clave TEXT NOT NULL,
               created_at TEXT DEFAULT (datetime('now'))
           )"""
    )
    execute("CREATE INDEX IF NOT EXISTS idx_antibot ON antibot_eventos (tipo, clave, created_at)")


def _contar(tipo, clave, segundos):
    fila = query(
        "SELECT COUNT(*) AS n FROM antibot_eventos WHERE tipo = ? AND clave = ? "
        "AND created_at > datetime('now', ?)",
        (tipo, clave, f"-{int(segundos)} seconds"), one=True,
    )
    return fila["n"] if fila else 0


def _registrar(tipo, clave):
    execute("INSERT INTO antibot_eventos (tipo, clave) VALUES (?, ?)", (tipo, clave))


def _limpiar_viejos():
    execute("DELETE FROM antibot_eventos WHERE created_at < datetime('now', '-3 days')")


def permitir(tipo, clave, maximo, segundos):
    """True y registra el evento si todavía no se llegó al máximo en la
    ventana; False (sin registrar) si se pasó."""
    _asegurar_tabla()
    if _contar(tipo, clave, segundos) >= maximo:
        return False
    _registrar(tipo, clave)
    return True


def _entero_env(nombre, defecto):
    try:
        return max(1, int(os.environ.get(nombre, defecto)))
    except (TypeError, ValueError):
        return defecto


def autorizar_envio(email, ip):
    """Chequea TODOS los topes antes de mandar un mail con código (registro,
    reenvío, ingreso sin validar, olvidé mi contraseña). Devuelve
    (True, "") y registra el envío, o (False, motivo) sin registrar nada.
    Hay que llamarlo ANTES de generar el código nuevo, así un envío bloqueado
    no invalida el código anterior."""
    _asegurar_tabla()
    email = (email or "").strip().lower()
    max_hora = _entero_env("ANTIBOT_MAX_MAILS_HORA", 25)
    max_dia = _entero_env("ANTIBOT_MAX_MAILS_DIA", 60)
    reglas = [
        ("mail_cooldown", email, 1, 60, "Esperá un minuto antes de pedir otro código."),
        ("mail_dest_hora", email, 3, 3600, "Ya se mandaron varios códigos a ese mail. Probá más tarde."),
        ("mail_dest_dia", email, 5, 86400, "Ya se mandaron varios códigos a ese mail. Probá mañana."),
        ("mail_ip_hora", ip, 5, 3600, "Demasiados pedidos desde tu conexión. Probá más tarde."),
        ("mail_ip_dia", ip, 15, 86400, "Demasiados pedidos desde tu conexión. Probá mañana."),
        ("mail_global_hora", "*", max_hora, 3600, "Hay mucha demanda ahora. Probá en un rato."),
        ("mail_global_dia", "*", max_dia, 86400, "Hay mucha demanda hoy. Probá mañana."),
    ]
    for tipo, clave, maximo, seg, motivo in reglas:
        if _contar(tipo, clave, seg) >= maximo:
            print(f"[antibot] envío bloqueado ({tipo}) ip={ip} mail={email!r}", flush=True)
            return False, motivo
    for tipo, clave, *_ in reglas:
        _registrar(tipo, clave)
    _limpiar_viejos()
    return True, ""


def permitir_intento(tipo, clave, maximo, segundos):
    """Atajo para limitar intentos (formularios, códigos mal tipeados)."""
    return permitir(tipo, clave, maximo, segundos)


# --- Turnstile --------------------------------------------------------------
def turnstile_site_key():
    return (os.environ.get("TURNSTILE_SITE_KEY") or "").strip()


def turnstile_activo():
    return bool(turnstile_site_key() and (os.environ.get("TURNSTILE_SECRET_KEY") or "").strip())


def verificar_turnstile(token, ip):
    """True si Cloudflare confirma que el desafío está resuelto. Sin claves
    configuradas devuelve True (y avisa en el log). Si Cloudflare no responde
    devuelve False: es preferible reintentar a dejar pasar a un bot."""
    secreta = (os.environ.get("TURNSTILE_SECRET_KEY") or "").strip()
    if not secreta or not turnstile_site_key():
        print("[antibot] Turnstile sin configurar (TURNSTILE_SITE_KEY / TURNSTILE_SECRET_KEY): no se exige", flush=True)
        return True
    token = (token or "").strip()
    if not token or len(token) > 2048:
        return False
    datos = urllib.parse.urlencode({"secret": secreta, "response": token, "remoteip": ip}).encode()
    try:
        req = urllib.request.Request(TURNSTILE_URL, data=datos, method="POST")
        with urllib.request.urlopen(req, timeout=6) as r:
            resp = json.loads(r.read().decode("utf-8"))
        ok = bool(resp.get("success"))
        if not ok:
            print(f"[antibot] Turnstile rechazado: {resp.get('error-codes')}", flush=True)
        return ok
    except Exception as e:
        print(f"[antibot] Turnstile no pudo verificarse: {e}", flush=True)
        return False


# --- Validación de textos ---------------------------------------------------
def _normalizar(txt):
    """Minúsculas y sin acentos, para comparar contra la lista de palabras."""
    nfd = unicodedata.normalize("NFD", txt.lower())
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


# Palabras que no tienen lugar en el nombre de una agencia de autos (spam de
# bonos/casinos/cripto y similares). Se buscan como palabra completa.
_PALABRAS_SPAM = {
    "bonus", "bono", "bonos", "code", "codes", "casino", "bet", "bets", "betting", "apuesta",
    "apuestas", "jackpot", "giveaway", "claim", "reward", "prize", "usdt", "btc", "bitcoin", "crypto", "cripto", "airdrop", "wallet", "forex", "invest",
    "inversion", "loan", "viagra", "porn", "sex", "sexo", "xxx", "telegram", "whatsapp",
    "http", "https", "www", "cashback", "withdraw",
}
_RE_URL = re.compile(r"(https?:|www\.|@|\.(com|net|org|ru|xyz|top|site|online|info|biz|cc|ly|me|io|co)\b|t\.me/|bit\.ly)", re.I)
# Caracteres permitidos en un nombre (letras latinas, números y puntuación común).
_RE_PERMITIDOS = re.compile(r"^[\w .,&'’\-/()+°ºª]+$", re.UNICODE)


def _solo_latino(txt):
    for c in txt:
        if c.isalpha():
            try:
                if not unicodedata.name(c).startswith("LATIN"):
                    return False
            except ValueError:
                return False
    return True


def _palabras_spam(txt):
    palabras = set(re.findall(r"[a-z0-9]+", _normalizar(txt)))
    return palabras & _PALABRAS_SPAM


def validar_nombre_agencia(nombre):
    """(nombre_limpio, error). Si hay error, `nombre_limpio` es None y el
    mensaje está listo para mostrar."""
    limpio = re.sub(r"\s+", " ", (nombre or "").strip())
    if not 3 <= len(limpio) <= 60:
        return None, "El nombre de la agencia tiene que tener entre 3 y 60 caracteres."
    if sum(c.isalpha() for c in limpio) < 3:
        return None, "El nombre de la agencia tiene que tener letras."
    if not _solo_latino(limpio):
        return None, "El nombre de la agencia solo puede tener letras del alfabeto latino."
    if _RE_URL.search(limpio):
        return None, "El nombre de la agencia no puede incluir links, mails ni direcciones web."
    if not _RE_PERMITIDOS.match(limpio):
        return None, "El nombre de la agencia tiene caracteres que no se aceptan (por ejemplo $, %, #, !, *, =)."
    if re.search(r"\d{5,}", limpio):
        return None, "El nombre de la agencia no puede tener números largos."
    letras = sum(c.isalpha() for c in limpio)
    digitos = sum(c.isdigit() for c in limpio)
    if digitos > letras:
        return None, "El nombre de la agencia tiene demasiados números."
    if re.search(r"(.)\1{4,}", limpio):
        return None, "El nombre de la agencia tiene caracteres repetidos."
    if limpio.upper() == limpio and len(limpio) > 25:
        return None, "Escribí el nombre de la agencia sin todo en mayúsculas."
    if _palabras_spam(limpio):
        return None, "Ese nombre no es válido para una agencia. Escribí el nombre real de tu agencia."
    return limpio, None


def validar_texto_libre(valor, etiqueta, maximo=120):
    """Control más liviano para dirección, ciudad y contacto: sin links, sin
    HTML y sin las palabras de spam. Devuelve (limpio, error)."""
    limpio = re.sub(r"\s+", " ", (valor or "").strip())
    if len(limpio) > maximo:
        return None, f"{etiqueta} es demasiado largo."
    if re.search(r"[<>{}\[\]|\\^`~$%*=]", limpio) or _RE_URL.search(limpio) or _palabras_spam(limpio):
        return None, f"{etiqueta} tiene caracteres o palabras que no se aceptan."
    if not _solo_latino(limpio):
        return None, f"{etiqueta} solo puede tener letras del alfabeto latino."
    return limpio, None


_RE_MAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def mail_valido(email):
    return bool(email) and len(email) <= 120 and bool(_RE_MAIL.match(email))
