"""Publicaciones por zona (Localidad + Radio) con avisos de DeAutos.com
(05/10/2026, prueba solo para la agencia 1 / Italia).

DeAutos es un agregador gratuito: sus páginas listan avisos de Mercado Libre,
Autocosmos, Kavak y particulares, y cada aviso trae su localidad. Con eso se
filtra por distancia a la localidad de la agencia.

Cuidados (mismos criterios que publicaciones_rg.py):
- Se lee la misma página pública que ve cualquiera (su robots.txt lo permite),
  con un User-Agent que se identifica.
- Una sola consulta al sitio por vehículo cada 24 h (tabla `rg_cache`, clave
  con prefijo "deautos|").
- Si el sitio cambia o no responde, devuelve ok=False sin romper la pantalla.
- Solo se muestran pocos avisos, siempre con link al original.

Autocosmos: no se consulta directo (sus términos exigen autorización escrita,
pedida el 05/10/2026). Sus avisos aparecen igual como "fuente" dentro de
DeAutos. Cuando autoricen se puede sumar un conector propio.
"""
import html
import json
import math
import re
import statistics
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timedelta

from publicaciones_rg import _SUBMODELOS, _palabras

CACHE_HORAS = 24
TIMEOUT = 8
MAX_AVISOS = 6
BASE = "https://deautos.com/autos-usados/"
_UA = "Mozilla/5.0 (compatible; AgencierosBot/1.0; +https://agencieros.net.ar)"

RADIOS = [25, 50, 100, 200, 300, 500, 1000]

# (nombre, provincia, lat, lon). Coordenadas aproximadas del centro de cada
# localidad (alcanza para radios de decenas de km).
LOCALIDADES = [
    # Santa Fe
    ("Rosario", "Santa Fe", -32.9442, -60.6505),
    ("Santa Fe", "Santa Fe", -31.6333, -60.7000),
    ("Rafaela", "Santa Fe", -31.2503, -61.4867),
    ("Venado Tuerto", "Santa Fe", -33.7456, -61.9688),
    ("Reconquista", "Santa Fe", -29.1500, -59.6500),
    ("Esperanza", "Santa Fe", -31.4500, -60.9333),
    ("Sunchales", "Santa Fe", -30.9456, -61.5603),
    ("Casilda", "Santa Fe", -33.0444, -61.1678),
    ("Cañada de Gómez", "Santa Fe", -32.8167, -61.4000),
    ("Villa Constitución", "Santa Fe", -33.2333, -60.3333),
    ("San Lorenzo", "Santa Fe", -32.7500, -60.7333),
    ("Granadero Baigorria", "Santa Fe", -32.8667, -60.7167),
    ("Funes", "Santa Fe", -32.9167, -60.8167),
    ("Roldán", "Santa Fe", -32.9000, -60.9000),
    ("Pérez", "Santa Fe", -32.9833, -60.7667),
    ("Villa Gobernador Gálvez", "Santa Fe", -33.0272, -60.6417),
    ("Capitán Bermúdez", "Santa Fe", -32.8167, -60.7167),
    ("Fray Luis Beltrán", "Santa Fe", -32.7833, -60.7333),
    ("Arroyo Seco", "Santa Fe", -33.1500, -60.5000),
    ("Firmat", "Santa Fe", -33.4585, -61.4833),
    ("Rufino", "Santa Fe", -34.2625, -62.7125),
    ("Gálvez", "Santa Fe", -32.0333, -61.2167),
    ("San Justo", "Santa Fe", -30.7833, -60.5933),
    ("Santo Tomé", "Santa Fe", -31.6667, -60.7667),
    ("San Jorge", "Santa Fe", -31.9000, -61.8667),
    ("Totoras", "Santa Fe", -32.5833, -61.1667),
    # Córdoba
    ("Córdoba", "Córdoba", -31.4201, -64.1888),
    ("Río Cuarto", "Córdoba", -33.1307, -64.3499),
    ("Villa María", "Córdoba", -32.4075, -63.2406),
    ("Villa Carlos Paz", "Córdoba", -31.4241, -64.4978),
    ("San Francisco", "Córdoba", -31.4281, -62.0827),
    ("Alta Gracia", "Córdoba", -31.6531, -64.4283),
    ("Jesús María", "Córdoba", -30.9817, -64.0953),
    ("Villa Allende", "Córdoba", -31.2931, -64.2956),
    ("Río Tercero", "Córdoba", -32.1736, -64.1144),
    ("Bell Ville", "Córdoba", -32.6264, -62.6881),
    ("Marcos Juárez", "Córdoba", -32.6967, -62.1017),
    ("La Falda", "Córdoba", -31.0911, -64.4894),
    ("Cosquín", "Córdoba", -31.2417, -64.4658),
    ("Morteros", "Córdoba", -30.7128, -61.9983),
    ("Oncativo", "Córdoba", -31.9142, -63.6836),
    ("Villa Dolores", "Córdoba", -31.9453, -65.1892),
    ("Río Segundo", "Córdoba", -31.6500, -63.9167),
    ("Villa Nueva", "Córdoba", -32.4333, -63.2500),
    ("Las Varillas", "Córdoba", -31.8719, -62.7203),
    ("Laboulaye", "Córdoba", -34.1274, -63.3911),
    ("Cruz del Eje", "Córdoba", -30.7261, -64.8067),
    ("General Cabrera", "Córdoba", -32.8167, -63.8667),
    ("Salsipuedes", "Córdoba", -31.1833, -64.2833),
    ("Tanti", "Córdoba", -31.3500, -64.5917),
    ("La Cumbre", "Córdoba", -30.9833, -64.5000),
    ("Villa Cura Brochero", "Córdoba", -31.7117, -65.0167),
    ("Mina Clavero", "Córdoba", -31.7228, -65.0058),
    ("Arroyito", "Córdoba", -31.4167, -63.0500),
    ("Villa del Rosario", "Córdoba", -31.5578, -63.5342),
    # Buenos Aires
    ("Ciudad de Buenos Aires", "Buenos Aires", -34.6037, -58.3816),
    ("La Plata", "Buenos Aires", -34.9205, -57.9536),
    ("Mar del Plata", "Buenos Aires", -38.0055, -57.5426),
    ("Bahía Blanca", "Buenos Aires", -38.7196, -62.2724),
    ("Tandil", "Buenos Aires", -37.3217, -59.1332),
    ("Pergamino", "Buenos Aires", -33.8895, -60.5736),
    ("San Nicolás", "Buenos Aires", -33.3333, -60.2167),
    ("Junín", "Buenos Aires", -34.5856, -60.9583),
    ("Olavarría", "Buenos Aires", -36.8927, -60.3225),
    ("Zárate", "Buenos Aires", -34.0981, -59.0286),
    ("Campana", "Buenos Aires", -34.1654, -58.9597),
    ("Luján", "Buenos Aires", -34.5703, -59.1050),
    ("Pilar", "Buenos Aires", -34.4587, -58.9142),
    ("San Isidro", "Buenos Aires", -34.4708, -58.5286),
    ("Vicente López", "Buenos Aires", -34.5267, -58.4725),
    ("Quilmes", "Buenos Aires", -34.7206, -58.2546),
    ("Lomas de Zamora", "Buenos Aires", -34.7609, -58.4017),
    ("Temperley", "Buenos Aires", -34.7833, -58.3833),
    ("Morón", "Buenos Aires", -34.6534, -58.6198),
    ("San Miguel", "Buenos Aires", -34.5439, -58.7125),
    ("Tigre", "Buenos Aires", -34.4260, -58.5797),
    ("Avellaneda", "Buenos Aires", -34.6623, -58.3656),
    ("Lanús", "Buenos Aires", -34.7000, -58.3917),
    ("San Justo (La Matanza)", "Buenos Aires", -34.6833, -58.5667),
    ("Merlo", "Buenos Aires", -34.6647, -58.7278),
    ("Escobar", "Buenos Aires", -34.3489, -58.7939),
    ("Chivilcoy", "Buenos Aires", -34.8964, -60.0178),
    ("Azul", "Buenos Aires", -36.7769, -59.8586),
    ("Necochea", "Buenos Aires", -38.5545, -58.7396),
    ("Trenque Lauquen", "Buenos Aires", -35.9708, -62.7342),
    ("Nueve de Julio", "Buenos Aires", -35.4442, -60.8833),
    ("Pehuajó", "Buenos Aires", -35.8108, -61.9000),
    ("Bragado", "Buenos Aires", -35.1167, -60.4833),
    ("Ramallo", "Buenos Aires", -33.4889, -60.0083),
    ("Baradero", "Buenos Aires", -33.8111, -59.5039),
    ("San Pedro", "Buenos Aires", -33.6784, -59.6653),
    ("Arrecifes", "Buenos Aires", -34.0667, -60.1000),
    ("Salto", "Buenos Aires", -34.2931, -60.2528),
    ("Rojas", "Buenos Aires", -34.1953, -60.7342),
    ("Lincoln", "Buenos Aires", -34.8667, -61.5333),
    ("General Pico", "La Pampa", -35.6567, -63.7569),
    # Entre Ríos
    ("Paraná", "Entre Ríos", -31.7333, -60.5333),
    ("Concordia", "Entre Ríos", -31.3929, -58.0209),
    ("Gualeguaychú", "Entre Ríos", -33.0094, -58.5172),
    ("Concepción del Uruguay", "Entre Ríos", -32.4833, -58.2333),
    ("Victoria", "Entre Ríos", -32.6167, -60.1500),
    ("Gualeguay", "Entre Ríos", -33.1411, -59.3133),
    # Capitales y ciudades del resto del país
    ("Santa Rosa", "La Pampa", -36.6167, -64.2833),
    ("Mendoza", "Mendoza", -32.8908, -68.8272),
    ("San Rafael", "Mendoza", -34.6177, -68.3301),
    ("San Miguel de Tucumán", "Tucumán", -26.8083, -65.2176),
    ("Salta", "Salta", -24.7821, -65.4232),
    ("San Salvador de Jujuy", "Jujuy", -24.1858, -65.2995),
    ("Neuquén", "Neuquén", -38.9516, -68.0591),
    ("San Juan", "San Juan", -31.5375, -68.5364),
    ("San Luis", "San Luis", -33.2950, -66.3356),
    ("La Rioja", "La Rioja", -29.4131, -66.8558),
    ("Catamarca", "Catamarca", -28.4696, -65.7852),
    ("Santiago del Estero", "Santiago del Estero", -27.7951, -64.2615),
    ("Resistencia", "Chaco", -27.4606, -58.9839),
    ("Corrientes", "Corrientes", -27.4692, -58.8306),
    ("Posadas", "Misiones", -27.3671, -55.8961),
    ("Oberá", "Misiones", -27.4871, -55.1199),
    ("Formosa", "Formosa", -26.1775, -58.1781),
    ("Rawson", "Chubut", -43.3002, -65.1023),
    ("Comodoro Rivadavia", "Chubut", -45.8641, -67.4966),
    ("Trelew", "Chubut", -43.2489, -65.3051),
    ("Viedma", "Río Negro", -40.8135, -62.9967),
    ("San Carlos de Bariloche", "Río Negro", -41.1335, -71.3103),
    ("Río Gallegos", "Santa Cruz", -51.6230, -69.2168),
    ("Ushuaia", "Tierra del Fuego", -54.8019, -68.3030),
    ("Río Grande", "Tierra del Fuego", -53.7877, -67.7095),
]

# Provincia -> ciudad capital usada cuando el aviso solo dice la provincia.
CAPITALES = {
    "Santa Fe": "Santa Fe", "Córdoba": "Córdoba", "Buenos Aires": "La Plata",
    "Entre Ríos": "Paraná", "La Pampa": "Santa Rosa", "Mendoza": "Mendoza",
    "Tucumán": "San Miguel de Tucumán", "Salta": "Salta", "Jujuy": "San Salvador de Jujuy",
    "Neuquén": "Neuquén", "San Juan": "San Juan", "San Luis": "San Luis", "La Rioja": "La Rioja",
    "Catamarca": "Catamarca", "Santiago del Estero": "Santiago del Estero", "Chaco": "Resistencia",
    "Corrientes": "Corrientes", "Misiones": "Posadas", "Formosa": "Formosa", "Chubut": "Rawson",
    "Río Negro": "Viedma", "Santa Cruz": "Río Gallegos", "Tierra del Fuego": "Ushuaia",
}
# Nombres que DeAutos usa y no son una provincia "normal".
_ALIAS_PROV = {
    "gran buenos aires": "Buenos Aires", "capital federal": "Buenos Aires", "caba": "Buenos Aires",
    "ciudad autonoma de buenos aires": "Buenos Aires",
}
_ALIAS_CIUDAD = {
    "san salvador de jujuy": "San Salvador de Jujuy", "9 de julio": "Nueve de Julio",
    "tucuman": "San Miguel de Tucumán",
}


def _n(texto):
    t = unicodedata.normalize("NFKD", str(texto or "").lower().strip())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t)


_POR_NOMBRE = {}
for _nom, _prov, _la, _lo in LOCALIDADES:
    _POR_NOMBRE.setdefault(_n(_nom), []).append((_nom, _prov, _la, _lo))
_PROVINCIAS_N = {_n(p): p for p in CAPITALES}


def nombres_localidades():
    """Lista ordenada 'Rosario, Santa Fe' para el selector."""
    return sorted({f"{n}, {p}" for n, p, _, _ in LOCALIDADES})


def resolver(texto, provincia=None):
    """'Salsipuedes, Córdoba' / 'Rosario' / 'Córdoba' -> dict
    {nombre, provincia, lat, lon, aprox} o None si no se reconoce.
    aprox=True cuando el texto solo traía la provincia (o "Gran Buenos
    Aires"): se usa su capital como punto de referencia."""
    partes = [p.strip() for p in str(texto or "").replace("·", "").split(",") if p.strip()]
    if provincia:
        partes.append(provincia)
    if not partes:
        return None
    ciudad_n = _n(partes[0])
    prov_n = _n(partes[-1]) if len(partes) > 1 else ""
    prov = _ALIAS_PROV.get(prov_n) or _PROVINCIAS_N.get(prov_n)

    def _punto(nombre, aprox):
        nom, pr, la, lo = _POR_NOMBRE[_n(nombre)][0]
        return {"nombre": nom, "provincia": pr, "lat": la, "lon": lo, "aprox": aprox}

    # "Gran Buenos Aires" / CABA
    if ciudad_n in ("gran buenos aires",):
        return _punto("Ciudad de Buenos Aires", True)
    if ciudad_n in ("caba", "capital federal", "ciudad autonoma de buenos aires"):
        return _punto("Ciudad de Buenos Aires", False)
    # Solo el nombre de una provincia: ubicación imprecisa -> capital
    if len(partes) == 1 and _PROVINCIAS_N.get(ciudad_n):
        return _punto(CAPITALES[_PROVINCIAS_N[ciudad_n]], True)
    # "San Juan Capital", "La Rioja Capital"
    if ciudad_n not in _POR_NOMBRE:
        ciudad_n = re.sub(r" capital$", "", ciudad_n)
    ciudad_n = _n(_ALIAS_CIUDAD.get(ciudad_n) or ciudad_n)
    candidatos = _POR_NOMBRE.get(ciudad_n, [])
    if candidatos:
        elegido = next((c for c in candidatos if prov and c[1] == prov), candidatos[0])
        return {"nombre": elegido[0], "provincia": elegido[1], "lat": elegido[2], "lon": elegido[3], "aprox": False}
    return None


def distancia_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------------------------------------------------------------- lectura

def _slug(texto):
    t = _n(texto).replace("&", " ")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def url_listado(marca, modelo):
    if marca and modelo:
        return f"{BASE}{_slug(marca)}-{_slug(modelo)}"
    return BASE + _slug(marca or modelo)


def _txt(fragmento):
    sin_tags = re.sub(r"<[^>]+>", " ", fragmento or "")
    return re.sub(r"\s+", " ", html.unescape(sin_tags)).strip()


def _campo(bloque, clase):
    m = re.search(r'class="%s[^"]*"[^>]*>(.*?)</(?:span|div|h3)>' % re.escape(clase), bloque, re.S)
    return _txt(m.group(1)) if m else ""


def parsear_listado(pagina):
    """[{titulo, version, anio, km, precio, moneda, fuente, loc, url}] a partir
    del HTML de DeAutos (tarjetas <a class="card card-link">)."""
    avisos = []
    for b in re.split(r'<a class="card card-link"', pagina)[1:]:
        m_url = re.search(r'href="(/auto/[^"]+)"', b)
        titulo = _campo(b, "card-title")
        if not (m_url and titulo):
            continue
        m_anio = re.match(r"(19[6-9]\d|20[0-4]\d)\s+(.*)", titulo)
        precio_txt = _txt((re.search(r'class="card-price">(.*?)</div>', b, re.S) or [None, ""])[1])
        moneda = "USD" if re.search(r"USD|U\$S|US\$", precio_txt) else ("ARS" if "$" in precio_txt else None)
        digitos = re.sub(r"\D", "", precio_txt)
        km_txt = _campo(b, "card-km")
        digitos_km = re.sub(r"\D", "", km_txt)
        avisos.append({
            "titulo": m_anio.group(2) if m_anio else titulo,
            "version": _campo(b, "card-version"),
            "anio": int(m_anio.group(1)) if m_anio else None,
            "km": int(digitos_km) if digitos_km else None,
            "precio": int(digitos) if digitos and moneda else None,
            "moneda": moneda,
            "fuente": _campo(b, "dealer-name"),
            "loc": _campo(b, "dealer-loc").lstrip("· ").strip(),
            "url": "https://deautos.com" + m_url.group(1),
        })
    return avisos


def _bajar(url):
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept-Language": "es-AR,es"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", errors="replace")


def _leer(url, query, execute):
    """Avisos del listado, con caché de 24 h. Devuelve (avisos, desde_cache)."""
    clave = "deautos|v1|" + url
    fila = query("SELECT datos, creado FROM rg_cache WHERE clave = ?", (clave,), one=True)
    if fila and datetime.fromisoformat(fila["creado"]) > datetime.utcnow() - timedelta(hours=CACHE_HORAS):
        return json.loads(fila["datos"]), True
    avisos = parsear_listado(_bajar(url))
    execute("INSERT OR REPLACE INTO rg_cache (clave, datos, creado) VALUES (?, ?, ?)",
            (clave, json.dumps(avisos, ensure_ascii=False), datetime.utcnow().isoformat()))
    return avisos, False


# ------------------------------------------------------------- selección

def _filtrar(avisos, marca, modelo, version, anio):
    pedidas_modelo = _palabras(modelo)
    pedidas_version = _palabras(version) - pedidas_modelo - _palabras(marca)
    salida = []
    for a in avisos:
        if not a.get("precio"):
            continue
        palabras = _palabras(a["titulo"] + " " + a.get("version", ""))
        if pedidas_modelo and not pedidas_modelo <= palabras:
            continue
        if any(s in palabras and s not in pedidas_modelo for s in _SUBMODELOS):
            continue
        dif_anio = abs(a["anio"] - int(anio)) if (anio and a.get("anio")) else 0
        if anio and a.get("anio") and dif_anio > 1:
            continue
        a = dict(a, _dif_anio=dif_anio, _coincide=len(pedidas_version & palabras))
        salida.append(a)
    return salida


def buscar(marca, modelo, version, anio, origen_txt, radio_km, query, execute, fuente=None):
    """Resultado para la pantalla. Nunca levanta error."""
    url = url_listado(marca, modelo)
    res = {"ok": False, "avisos": [], "url_busqueda": url, "origen": None, "radio": radio_km,
           "motivo": None, "leidos": 0, "en_radio": 0, "fuera_de_radio": 0, "sin_ubicar": 0,
           "mediana_ars": None, "fuentes": []}
    origen = resolver(origen_txt)
    if not origen:
        res["motivo"] = "Elegí una Localidad de la lista para calcular el radio."
        return res
    res["origen"] = {"nombre": origen["nombre"], "provincia": origen["provincia"]}
    if not modelo:
        res["motivo"] = "Falta el modelo."
        return res
    try:
        avisos, cache = _leer(url, query, execute)
    except urllib.error.HTTPError as e:
        if e.code == 404 and marca:  # no hay página del modelo: se prueba la de la marca
            try:
                url = url_listado(marca, "")
                res["url_busqueda"] = url
                avisos, cache = _leer(url, query, execute)
            except Exception as e2:
                print(f"[zona_deautos] No se pudo leer {url}: {e2}")
                res["motivo"] = "DeAutos no tiene esa página o no respondió."
                return res
        else:
            res["motivo"] = f"DeAutos respondió HTTP {e.code}."
            return res
    except Exception as e:
        print(f"[zona_deautos] No se pudo leer {url}: {e}")
        res["motivo"] = "DeAutos no respondió."
        return res
    res["leidos"] = len(avisos)
    candidatos = _filtrar(avisos, marca, modelo, version, anio)
    if fuente:
        candidatos = [a for a in candidatos if _n(a.get("fuente")) == _n(fuente)]
    en_radio = []
    for a in candidatos:
        ubic = resolver(a.get("loc"))
        if not ubic:
            res["sin_ubicar"] += 1
            continue
        d = distancia_km(origen["lat"], origen["lon"], ubic["lat"], ubic["lon"])
        if d > radio_km:
            res["fuera_de_radio"] += 1
            continue
        en_radio.append(dict(a, distancia_km=round(d), aprox=ubic["aprox"], ciudad=ubic["nombre"]))
    en_radio.sort(key=lambda a: (a["_dif_anio"], -a["_coincide"], a["distancia_km"]))
    res["en_radio"] = len(en_radio)
    res["fuentes"] = sorted({a["fuente"] for a in candidatos if a.get("fuente")})
    ars = [a["precio"] for a in en_radio if a["moneda"] == "ARS" and a["_dif_anio"] == 0]
    if len(ars) >= 3:
        res["mediana_ars"] = int(statistics.median(ars))
    res["avisos"] = [{k: v for k, v in a.items() if not k.startswith("_")} for a in en_radio[:MAX_AVISOS]]
    res["ok"] = bool(res["avisos"])
    if not res["ok"]:
        res["motivo"] = "Sin avisos en ese radio (DeAutos tiene pocos avisos todavía)."
    return res
