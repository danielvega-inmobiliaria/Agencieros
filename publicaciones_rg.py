"""Publicaciones reales de RosarioGarage para la Consulta de precios y la
Tasación (28/09/2026, pedido de Daniel).

MercadoLibre bloquea su buscador por API (403) y Facebook Marketplace exige
iniciar sesión, así que la fuente que se puede leer hoy es RosarioGarage: se
lee la misma página de resultados que ve cualquier persona (su robots.txt
permite recorrer el sitio) y se toman 3 avisos en pesos del mismo modelo y
año, los más parecidos a la versión consultada.

Cuidados:
- Una sola consulta al sitio por vehículo cada 24 h (tabla `rg_cache`).
- Si RosarioGarage cambia el diseño de su página o no responde, devuelve
  una lista vacía y la pantalla simplemente no muestra el bloque.
"""
import html
import json
import re
import unicodedata
import urllib.request
from datetime import datetime, timedelta

from comparables import _url_rosariogarage

CACHE_HORAS = 24
TIMEOUT = 8
MAX_AVISOS = 3
_UA = "Mozilla/5.0 (compatible; AgencierosBot/1.0; +https://agencieros.net.ar)"

# Palabras que indican otro modelo distinto aunque contenga el buscado
# (ej. "corolla" también trae "Corolla Cross").
_SUBMODELOS = {"cross", "sw", "country", "trend", "sportwagen", "tracker"}
_SINONIMOS = {
    "hybrid": "hibrido", "hibrida": "hibrido", "hev": "hibrido", "hv": "hibrido", "hibrid": "hibrido",
    "hybri": "hibrido", "cvt": "at", "ecvt": "at", "automatico": "at", "aut": "at",
}


def asegurar_tabla(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS rg_cache (
               clave TEXT PRIMARY KEY, datos TEXT NOT NULL, creado TEXT NOT NULL)"""
    )


def _norm(texto):
    t = unicodedata.normalize("NFKD", str(texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t


def _palabras(texto):
    out = set()
    for p in re.findall(r"[a-z0-9\.\-/]+", _norm(texto)):
        p = p.strip(".-/").replace("-", "")
        if not p:
            continue
        out.add(_SINONIMOS.get(p, p))
    return out


def _texto(fragmento):
    sin_tags = re.sub(r"<[^>]+>", " ", fragmento)
    return re.sub(r"\s+", " ", html.unescape(sin_tags)).strip()


def parsear_listado(pagina):
    """Devuelve [{id, titulo, detalle, anio, km, precio, moneda, url, foto}]
    a partir del HTML del listado de RosarioGarage."""
    avisos = []
    bloques = re.split(r'<div class="col box_aviso_base', pagina)[1:]
    for b in bloques:
        m_id = re.search(r'data-rel="(\d+)"', b)
        m_tit = re.search(r'class="box_aviso_tit">(.*?)</a>', b, re.S)
        m_precio = re.search(r'class="precio[^"]*">\s*<a[^>]*>(.*?)</a>', b, re.S)
        if not (m_id and m_tit and m_precio):
            continue
        m_nombre = re.search(r'<strong[^>]*>(.*?)</strong>', m_tit.group(1), re.S)
        titulo = _texto(m_nombre.group(1)) if m_nombre else ""
        detalle = _texto(re.sub(r'<strong[^>]*>.*?</strong>', "", m_tit.group(1), flags=re.S))
        detalle = re.sub(r"\s+,", ",", detalle).strip(" ,")
        precio_txt = _texto(m_precio.group(1))
        moneda = "USD" if re.search(r"U\$S|USD|US\$", precio_txt) else ("ARS" if "$" in precio_txt else None)
        digitos = re.sub(r"\D", "", precio_txt)
        precio = int(digitos) if digitos and moneda else None
        m_km = re.search(r"([\d\.]+)\s*km", detalle)
        km = int(m_km.group(1).replace(".", "")) if m_km else None
        m_anio = re.search(r"\b(19[89]\d|20[0-4]\d)\b", detalle)
        # Las fotos se cargan con "lazyload": la real está en data-src y el
        # src suele ser un logo de relleno (default-553x380.png). Fix 28/09/2026.
        m_foto = (re.search(r'<img[^>]*\sdata-src="([^"]+)"', b)
                  or re.search(r'<img[^>]*\ssrc="([^"]+)"', b))
        foto = m_foto.group(1) if m_foto else None
        if foto and ("/statics/" in foto or "default-" in foto):
            foto = None
        avisos.append({
            "id": m_id.group(1),
            "titulo": titulo,
            "detalle": detalle,
            "anio": int(m_anio.group(1)) if m_anio else None,
            "km": km,
            "precio": precio,
            "moneda": moneda,
            "url": f"https://www.rosariogarage.com/index.php?action=carro/showProduct&itmId={m_id.group(1)}",
            "foto": foto,
        })
    return avisos


def elegir(avisos, marca, modelo, version, anio, valor_tabla=None):
    """Filtra y ordena: solo pesos, mismo año, sin submodelos que no se
    pidieron (Cross, SW...), sin precios absurdos, y los más parecidos a la
    versión primero."""
    pedidas_modelo = _palabras(modelo)
    pedidas_version = _palabras(version) - pedidas_modelo - _palabras(marca)
    elegidos = []
    for a in avisos:
        if a["moneda"] != "ARS" or not a["precio"]:
            continue
        if anio and a["anio"] and str(a["anio"]) != str(anio):
            continue
        palabras_aviso = _palabras(a["titulo"] + " " + a["detalle"])
        if not pedidas_modelo <= palabras_aviso:
            continue
        if any(s in palabras_aviso and s not in pedidas_modelo for s in _SUBMODELOS):
            continue
        if a["precio"] < 1_000_000 or a["precio"] >= 900_000_000:
            continue
        if valor_tabla and not (valor_tabla / 2.5 <= a["precio"] <= valor_tabla * 2.5):
            continue
        coincidencias = len(pedidas_version & palabras_aviso)
        elegidos.append((coincidencias, a))
    elegidos.sort(key=lambda t: (-t[0], t[1]["km"] if t[1]["km"] is not None else 10**9))
    return [a for _, a in elegidos[:MAX_AVISOS]]


def _bajar(url):
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept-Language": "es-AR,es"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", errors="replace")


def publicaciones(marca, modelo, version, anio, valor_tabla=None):
    """{"ok": bool, "avisos": [...], "url_busqueda": str}. Nunca levanta error."""
    from database import query, execute
    url = _url_rosariogarage(marca, modelo, anio)
    resultado = {"ok": False, "avisos": [], "url_busqueda": url}
    if not modelo:
        return resultado
    clave = "v2|" + url  # v2: la cache anterior tenía la foto de relleno
    try:
        fila = query("SELECT datos, creado FROM rg_cache WHERE clave = ?", (clave,), one=True)
        if fila and datetime.fromisoformat(fila["creado"]) > datetime.utcnow() - timedelta(hours=CACHE_HORAS):
            avisos = json.loads(fila["datos"])
        else:
            avisos = parsear_listado(_bajar(url))
            execute("INSERT OR REPLACE INTO rg_cache (clave, datos, creado) VALUES (?, ?, ?)",
                    (clave, json.dumps(avisos, ensure_ascii=False), datetime.utcnow().isoformat()))
    except Exception as e:
        print(f"[rosariogarage] No se pudo leer {url}: {e}")
        return resultado
    try:
        vt = float(valor_tabla) if valor_tabla else None
    except ValueError:
        vt = None
    resultado["avisos"] = elegir(avisos, marca, modelo, version, anio, vt)
    resultado["ok"] = bool(resultado["avisos"])
    return resultado
