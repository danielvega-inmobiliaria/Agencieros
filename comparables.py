from urllib.parse import quote_plus


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
        {"label": "RosarioGarage", "url": f"https://www.rosariogarage.com/index.php?action=finder/search&itmModelDesc={quote_plus(consulta)}"},
        {"label": "Facebook Marketplace", "url": f"https://www.facebook.com/marketplace/search/?query={quote_plus(consulta)}"},
    ]
