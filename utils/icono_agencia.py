"""Ícono propio de cada agencia (25/11/2026): favicon, ícono de la pantalla de
inicio y de la app instalada, armados con el LOGO de la agencia.

Se genera al vuelo con Pillow (cuadrado, logo centrado con margen) y se guarda en
memoria. Si la agencia no tiene logo o el archivo no está, devuelve None y la
web usa el ícono de AGENCIEROS.
"""
import io
import os

TAMANOS = (48, 180, 192, 512)
_cache = {}


def _hex_rgb(h):
    h = (h or "#1f4fa8").lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def png_de_logo(ruta, px, color_marca="#1f4fa8"):
    """PNG (bytes) cuadrado de `px` con el logo de `ruta`; None si no se puede."""
    if px not in TAMANOS or not ruta or not os.path.isfile(ruta):
        return None
    clave = (ruta, os.path.getmtime(ruta), px, color_marca)
    if clave in _cache:
        return _cache[clave]
    try:
        from PIL import Image
        logo = Image.open(ruta).convert("RGBA")
    except Exception:
        return None
    # Recorta los bordes transparentes para que el logo ocupe bien el cuadrado.
    caja = logo.getchannel("A").getbbox()
    if caja:
        logo = logo.crop(caja)
    # Fondo blanco; si el logo es casi todo blanco (y transparente) se usa el color de marca.
    fondo = (255, 255, 255)
    px_op = [p for p in logo.getdata() if p[3] > 200]
    if px_op and logo.getchannel("A").getextrema()[0] < 40:
        brillo = sum(0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2] for p in px_op) / len(px_op)
        if brillo > 225:
            fondo = _hex_rgb(color_marca)
    lienzo = Image.new("RGBA", (px, px), fondo + (255,))
    margen = round(px * 0.14)          # deja la zona segura de los íconos «maskable»
    util = px - 2 * margen
    esc = min(util / logo.width, util / logo.height)
    nuevo = logo.resize((max(1, round(logo.width * esc)), max(1, round(logo.height * esc))), Image.LANCZOS)
    lienzo.alpha_composite(nuevo, ((px - nuevo.width) // 2, (px - nuevo.height) // 2))
    buf = io.BytesIO()
    lienzo.convert("RGB").save(buf, "PNG", optimize=True)
    datos = buf.getvalue()
    if len(_cache) > 200:
        _cache.clear()
    _cache[clave] = datos
    return datos
