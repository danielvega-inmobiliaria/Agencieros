from urllib.parse import quote_plus, urlencode

# Ids de marca del buscador de RosarioGarage (select "Marca" de
# rosariogarage.com/Autos, relevado 24/09/2026). Su campo de texto
# (`itmModelDesc`) busca SOLO en el modelo/versión del aviso, no en la
# marca: por eso "Toyota Etios 1.5 4 PTAS PLATINUM 2018" como texto libre
# no encontraba nunca nada. Ahora se arma igual que su propio formulario:
# marca por id + modelo como texto + año desde/hasta.
_MARCAS_ROSARIOGARAGE = {
    "acura": 1001, "alfa romeo": 1003, "arcfox": 2143, "audi": 1008, "baic": 2095, "baw": 2142,
    "bentley": 1013, "bmw": 1015, "byd": 2133, "changan": 2108, "chery": 1019, "chevrolet": 1020,
    "chrysler": 1021, "citroen": 1023, "coradir": 2115, "dacia": 1024, "daewoo": 1025,
    "daihatsu": 1026, "dfsk": 2100, "dodge": 1031, "ds": 2099, "ferrari": 1035, "fiat": 1036,
    "ford": 1037, "forthing": 2137, "gac": 2132, "geely": 2092, "gmc": 1040, "haval": 2097,
    "honda": 1045, "hyundai": 1048, "infiniti": 1050, "isard": 2073, "isuzu": 1052, "jac": 1055,
    "jaguar": 1056, "kia": 1058, "leapmotor": 2145, "lexus": 1063, "lifan": 2093,
    "maserati": 1068, "maxus": 2146, "mazda": 1070, "mercedes benz": 1071, "mercedes-benz": 1071,
    "mg": 1074, "mini": 1075, "mitsubishi": 1076, "mustang": 2070, "nissan": 1080, "opel": 1083,
    "peugeot": 1086, "pontiac": 1089, "porsche": 1090, "renault": 1095, "rover": 1097,
    "saab": 1099, "seat": 1103, "shineray": 2094, "smart": 1107, "soueast": 2107,
    "subaru": 1110, "suzuki": 1111, "toyota": 1114, "volkswagen": 1118, "vw": 1118, "volvo": 1119,
}


def _url_rosariogarage(marca, modelo, anio):
    """Búsqueda en RosarioGarage con los mismos parámetros que usa su
    formulario (probado 24/09/2026: Toyota + "etios" + 2017-2019 = 43
    avisos; Toyota + "hilux" = también trae camionetas). Sin marca conocida
    se busca solo por modelo."""
    params = {"action": "finder/search", "o": 0}
    marca_id = _MARCAS_ROSARIOGARAGE.get((marca or "").strip().lower())
    if marca_id:
        params["mrkId"] = marca_id
        texto = modelo or ""
    else:
        texto = " ".join(p for p in [marca, modelo] if p)
    if texto:
        params["itmModelDesc"] = texto.strip().lower()
    if anio:
        params["year[from]"] = anio
        params["year[to]"] = anio
    return "https://www.rosariogarage.com/index.php?" + urlencode(params)


def links_comparables(marca, modelo, version, anio):
    """Búsquedas rápidas de precios de referencia en la web (MercadoLibre,
    RosarioGarage, Facebook Marketplace) para un vehículo puntual. No
    hacemos scraping automático (es frágil y varios sitios lo bloquean) --
    generamos el link de búsqueda directa a cada sitio (nada de pasar por
    Google) y lo abre el agenciero en una pestaña nueva, para cotejar a ojo
    contra el valor de tabla (o como único dato cuando no hay valor de tabla
    -- ver routes/precios.py, pedido de Daniel 22/09/2026: mientras no esté
    resuelto el listado de InfoAuto, esto es lo que hay para estimar un
    vehículo que no está en la base de precios).

    RosarioGarage no tiene un buscador de texto libre documentado en la UI,
    pero su motor interno sí lo acepta por query string
    (?action=finder/search&itmModelDesc=<texto>) y devuelve resultados reales
    del sitio combinando marca+modelo (probado a mano: "ford focus" -> 6
    avisos de Ford Focus). Facebook Marketplace tiene su propio buscador en
    /marketplace/search/?query=<texto> -- como el agenciero ya suele estar
    logueado en su Facebook, entra directo a los resultados en vez de pasar
    por una búsqueda de Google que muchas veces trae resultados viejos o
    de otra ciudad.

    Compartida (routes/tomas.py y routes/precios.py) -- antes vivía solo en
    routes/tomas.py como _links_comparables."""
    partes = [p for p in [marca, modelo, version, str(anio) if anio else ""] if p]
    consulta = " ".join(partes).strip()
    if not consulta:
        return []
    slug_ml = quote_plus(consulta).replace("+", "-")
    return [
        {"label": "MercadoLibre", "url": f"https://listado.mercadolibre.com.ar/{slug_ml}"},
        {"label": "RosarioGarage", "url": _url_rosariogarage(marca, modelo, anio)},
        {"label": "Facebook Marketplace", "url": f"https://www.facebook.com/marketplace/search/?query={quote_plus(consulta)}"},
    ]
