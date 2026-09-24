"""Rango de precios de mercado con la API oficial de MercadoLibre (24/09/2026).

Trae los avisos reales de "Autos y Camionetas" (categoría MLA1744) para
marca + modelo (+ versión si alcanza) + año y calcula un rango: mínimo,
rango típico (percentil 25 a 75), mediana, promedio y máximo. Se muestra al
lado del valor de tabla en Consulta de precios y en la Tasación.

Credenciales: variables de entorno ML_CLIENT_ID / ML_CLIENT_SECRET (app
"AGENCIEROS" de developers.mercadolibre.com.ar). Nunca en el repo.
Sin credenciales, `disponible()` da False y la UI no muestra nada.

Token (en este orden):
  1. Token de usuario guardado por /ml/conectar -> /ml/callback (Authorization
     Code + refresh_token, se renueva solo). Es el más confiable: desde 2025
     MercadoLibre rechaza (403) el buscador público sin token.
  2. Client Credentials (token de la app, sin usuario) como respaldo.

Precios: se usan solo avisos en pesos. Los avisos en dólares se cuentan
aparte (no se convierten: el tipo de cambio que usa cada agenciero varía)
y se descartan outliers típicos de ML (anticipos, "cuotas", precios
simbólicos) con un filtro alrededor de la mediana.

Cache: 24 h por búsqueda en la tabla `ml_cache`, para no pegarle a la API en
cada consulta. Solo `urllib` de la librería estándar (sin dependencias nuevas).
"""

import json
import os
import statistics
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://api.mercadolibre.com"
AUTH_URL = "https://auth.mercadolibre.com.ar/authorization"
CATEGORIA_AUTOS = "MLA1744"
CACHE_SEGUNDOS = 24 * 3600
MIN_AVISOS_VERSION = 5   # con menos avisos de la versión exacta, se amplía a todo el modelo
MIN_AVISOS_RANGO = 3     # con menos de esto no se muestra rango (poco confiable)
TIMEOUT = 8

_token_app = {"access_token": None, "expira": 0}


def _cred():
    return os.environ.get("ML_CLIENT_ID", "").strip(), os.environ.get("ML_CLIENT_SECRET", "").strip()


def disponible():
    cid, sec = _cred()
    return bool(cid and sec)


def redirect_uri():
    base = os.environ.get("APP_URL", "https://app.agencieros.net.ar").rstrip("/")
    return os.environ.get("ML_REDIRECT_URI", f"{base}/ml/callback")


# ---------------------------------------------------------------- HTTP ----
def _http(url, data=None, token=None):
    """Devuelve (status, json|None). Nunca levanta excepción."""
    headers = {"Accept": "application/json", "User-Agent": "Agencieros/1.0"}
    body = None
    if data is not None:
        body = urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urlopen(Request(url, data=body, headers=headers), timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "null")
    except HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "null")
        except Exception:
            return e.code, None
    except (URLError, TimeoutError, OSError, ValueError):
        return 0, None


# -------------------------------------------------------------- tokens ----
def _db():
    from database import query, execute
    return query, execute


def asegurar_tablas(conn):
    """Llamada desde database.init_db()."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS ml_tokens (
               id INTEGER PRIMARY KEY CHECK (id = 1),
               access_token TEXT, refresh_token TEXT, expira REAL,
               user_id TEXT, actualizado TEXT)"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS ml_cache (
               clave TEXT PRIMARY KEY, datos TEXT, creado REAL)"""
    )


def url_autorizacion(state):
    cid, _ = _cred()
    return AUTH_URL + "?" + urlencode(
        {"response_type": "code", "client_id": cid, "redirect_uri": redirect_uri(), "state": state}
    )


def _guardar_token_usuario(j):
    query, execute = _db()
    execute(
        """INSERT INTO ml_tokens (id, access_token, refresh_token, expira, user_id, actualizado)
           VALUES (1, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(id) DO UPDATE SET access_token=excluded.access_token,
             refresh_token=COALESCE(excluded.refresh_token, ml_tokens.refresh_token),
             expira=excluded.expira, user_id=COALESCE(excluded.user_id, ml_tokens.user_id),
             actualizado=excluded.actualizado""",
        (j["access_token"], j.get("refresh_token"), time.time() + int(j.get("expires_in", 21600)) - 120,
         str(j.get("user_id") or "") or None),
    )


def canjear_codigo(code):
    """Paso final de /ml/callback. Devuelve (ok, mensaje)."""
    cid, sec = _cred()
    st, j = _http(f"{API}/oauth/token", data={
        "grant_type": "authorization_code", "client_id": cid, "client_secret": sec,
        "code": code, "redirect_uri": redirect_uri(),
    })
    if st == 200 and j and j.get("access_token"):
        _guardar_token_usuario(j)
        return True, "Cuenta de MercadoLibre conectada."
    return False, f"MercadoLibre rechazó el código (HTTP {st}: {(j or {}).get('message') or (j or {}).get('error') or 'sin detalle'})."


def _token_usuario():
    query, _ = _db()
    row = query("SELECT * FROM ml_tokens WHERE id = 1", one=True)
    if not row or not row["access_token"]:
        return None
    if row["expira"] and row["expira"] > time.time():
        return row["access_token"]
    if not row["refresh_token"]:
        return None
    cid, sec = _cred()
    st, j = _http(f"{API}/oauth/token", data={
        "grant_type": "refresh_token", "client_id": cid, "client_secret": sec,
        "refresh_token": row["refresh_token"],
    })
    if st == 200 and j and j.get("access_token"):
        _guardar_token_usuario(j)
        return j["access_token"]
    return None


def _token_app_cc():
    if _token_app["access_token"] and _token_app["expira"] > time.time():
        return _token_app["access_token"]
    cid, sec = _cred()
    st, j = _http(f"{API}/oauth/token", data={
        "grant_type": "client_credentials", "client_id": cid, "client_secret": sec,
    })
    if st == 200 and j and j.get("access_token"):
        _token_app["access_token"] = j["access_token"]
        _token_app["expira"] = time.time() + int(j.get("expires_in", 21600)) - 120
        return j["access_token"]
    return None


def tokens_disponibles():
    """[(tipo, token)] en orden de preferencia."""
    out = []
    t = _token_usuario()
    if t:
        out.append(("usuario", t))
    t = _token_app_cc()
    if t:
        out.append(("app", t))
    return out


def estado_conexion():
    query, _ = _db()
    row = query("SELECT user_id, actualizado, expira FROM ml_tokens WHERE id = 1", one=True)
    return {
        "credenciales": disponible(),
        "usuario_conectado": bool(row),
        "user_id": row["user_id"] if row else None,
        "actualizado": row["actualizado"] if row else None,
    }


# ------------------------------------------------------------ búsqueda ----
def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(s.split())


def _buscar(q, anio, token):
    params = {"category": CATEGORIA_AUTOS, "q": q, "limit": 50}
    if anio:
        params["VEHICLE_YEAR"] = f"{anio}-{anio}"
    return _http(f"{API}/sites/MLA/search?{urlencode(params)}", token=token)


def _km(item):
    for a in item.get("attributes") or []:
        if a.get("id") == "KILOMETERS":
            try:
                return int(float(str(a.get("value_struct", {}).get("number") or a.get("value_name", "")).split()[0].replace(".", "")))
            except (ValueError, IndexError, AttributeError):
                return None
    return None


def _anio_item(item):
    for a in item.get("attributes") or []:
        if a.get("id") == "VEHICLE_YEAR":
            try:
                return int(a.get("value_name"))
            except (TypeError, ValueError):
                return None
    return None


def _percentil(ordenados, p):
    if not ordenados:
        return None
    k = (len(ordenados) - 1) * p
    f = int(k)
    c = min(f + 1, len(ordenados) - 1)
    return ordenados[f] + (ordenados[c] - ordenados[f]) * (k - f)


def calcular_rango(items, anio=None):
    """items = results de /sites/MLA/search. Devuelve el dict del rango."""
    ars, usd = [], 0
    for it in items:
        if anio and _anio_item(it) not in (None, int(anio)):
            continue
        precio = it.get("price")
        if not precio:
            continue
        if it.get("currency_id") == "USD":
            usd += 1
            continue
        if it.get("currency_id") != "ARS":
            continue
        ars.append(it)
    if not ars:
        return {"n": 0, "n_usd": usd}
    med = statistics.median(i["price"] for i in ars)
    # Outliers: anticipos/cuotas (muy bajos) y precios tipeados de más.
    buenos = [i for i in ars if 0.5 * med <= i["price"] <= 2.0 * med]
    descartados = len(ars) - len(buenos)
    precios = sorted(i["price"] for i in buenos)
    kms = [k for k in (_km(i) for i in buenos) if k]
    muestras = sorted(buenos, key=lambda i: abs(i["price"] - statistics.median(precios)))[:5]
    return {
        "n": len(precios), "n_usd": usd, "descartados": descartados,
        "minimo": precios[0], "maximo": precios[-1],
        "p25": round(_percentil(precios, 0.25)), "p75": round(_percentil(precios, 0.75)),
        "mediana": round(statistics.median(precios)), "promedio": round(statistics.mean(precios)),
        "km_promedio": round(statistics.mean(kms)) if kms else None,
        "muestras": [
            {"titulo": i.get("title"), "precio": i["price"], "url": i.get("permalink"), "km": _km(i)}
            for i in sorted(muestras, key=lambda i: i["price"])
        ],
    }


def _cache_get(clave):
    query, _ = _db()
    row = query("SELECT datos, creado FROM ml_cache WHERE clave = ?", (clave,), one=True)
    if row and time.time() - row["creado"] < CACHE_SEGUNDOS:
        return json.loads(row["datos"])
    return None


def _cache_set(clave, datos):
    _, execute = _db()
    execute("INSERT OR REPLACE INTO ml_cache (clave, datos, creado) VALUES (?, ?, ?)",
            (clave, json.dumps(datos), time.time()))


def rango_mercado(marca, modelo, version="", anio=""):
    """Dict listo para la UI. Siempre tiene "disponible" y "ok"."""
    if not disponible():
        return {"disponible": False, "ok": False}
    base = " ".join(p for p in [marca, modelo] if p).strip()
    if not base:
        return {"disponible": True, "ok": False, "motivo": "Falta marca/modelo."}
    clave = _norm(f"{base}|{version}|{anio}")
    en_cache = _cache_get(clave)
    if en_cache:
        en_cache["cache"] = True
        return en_cache

    tokens = tokens_disponibles()
    if not tokens:
        return {"disponible": True, "ok": False,
                "motivo": "MercadoLibre no entregó un token (revisar ML_CLIENT_ID / ML_CLIENT_SECRET)."}

    ultimo_error = None
    for tipo, token in tokens:
        intentos = []
        if version:
            intentos.append(("version", f"{base} {version}"))
        intentos.append(("modelo", base))
        for alcance, q in intentos:
            st, j = _buscar(q, anio, token)
            if st != 200 or not isinstance(j, dict):
                ultimo_error = st
                break  # probar con el siguiente token
            rango = calcular_rango(j.get("results") or [], anio)
            if rango["n"] >= (MIN_AVISOS_VERSION if alcance == "version" else MIN_AVISOS_RANGO) or alcance == "modelo":
                ok = rango["n"] >= MIN_AVISOS_RANGO
                datos = {
                    "disponible": True, "ok": ok, "alcance": alcance, "consulta": q, "anio": anio,
                    "total_ml": (j.get("paging") or {}).get("total"), "token": tipo,
                    "motivo": None if ok else "Muy pocos avisos en pesos para armar un rango confiable.",
                    **rango,
                }
                _cache_set(clave, datos)
                datos["cache"] = False
                return datos
    motivo = ("MercadoLibre rechazó la búsqueda (403). Conectá la cuenta de ML desde Admin → MercadoLibre."
              if ultimo_error in (401, 403) else f"MercadoLibre no respondió (HTTP {ultimo_error}).")
    return {"disponible": True, "ok": False, "motivo": motivo, "http": ultimo_error}


def diagnostico():
    """Pruebas contra la API real para ver QUÉ rechaza ML y por qué (24/09/2026:
    /sites/MLA/search dio 403 con token de app y también con token de usuario).
    Devuelve [(descripcion, tipo_token, http, mensaje)] -- sin tokens ni secretos."""
    out = []
    pruebas = [
        ("Buscar 'toyota etios' en Autos (categoría + año)", f"{API}/sites/MLA/search?" + urlencode({"category": CATEGORIA_AUTOS, "q": "toyota etios", "VEHICLE_YEAR": "2018-2018", "limit": 1})),
        ("Buscar 'toyota etios' sin categoría", f"{API}/sites/MLA/search?" + urlencode({"q": "toyota etios", "limit": 1})),
        ("Listar categoría Autos (sin texto)", f"{API}/sites/MLA/search?" + urlencode({"category": CATEGORIA_AUTOS, "limit": 1})),
        ("Datos de la categoría Autos (no es búsqueda)", f"{API}/categories/{CATEGORIA_AUTOS}"),
        ("Mi usuario (/users/me)", f"{API}/users/me"),
    ]
    tokens = tokens_disponibles() or [("sin token", None)]
    for tipo, token in tokens:
        for desc, url in pruebas:
            st, j = _http(url, token=token)
            msg = ""
            if isinstance(j, dict):
                if st == 200:
                    if "results" in j:
                        msg = f"OK: {(j.get('paging') or {}).get('total')} avisos en total"
                    else:
                        msg = "OK"
                else:
                    msg = " / ".join(str(j.get(k)) for k in ("message", "error", "blocked_by", "code") if j.get(k))
            out.append((desc, tipo, st, msg))
    return out

