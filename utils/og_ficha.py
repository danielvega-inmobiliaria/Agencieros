"""Imagen de la vista previa del link de la ficha (Open Graph, 1200x630).

Al compartir el link de una ficha por WhatsApp/Facebook, en lugar de mostrar
solo la primera foto se muestra una tarjeta armada con foto, logo de la
agencia, título, datos, precio, forma de pago y «Ver ficha completa»
(pedido de Daniel, 16/11/2026: que se vea lo importante sin abrir el link).

`generar(d)` devuelve los bytes de un JPEG. `d` es un dict con:
titulo, datos, precio, plan_1, plan_2, agencia, foto_path, logo_path.
Todo es opcional salvo titulo. Si falta Pillow, quien llama debe atrapar la
excepción y caer a la foto sola.
"""
import io
import os

from PIL import Image, ImageDraw, ImageFont, ImageOps

_FUENTES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "fonts")
W, H = 1200, 630
ORO = (240, 199, 107)
NAVY = (11, 20, 32)


def _fuente(nombre, tam):
    return ImageFont.truetype(os.path.join(_FUENTES, nombre), tam)


def _ajustar(draw, texto, nombre, tam, ancho_max, minimo=30):
    """Achica la fuente hasta que el texto entre en `ancho_max`."""
    while tam > minimo:
        f = _fuente(nombre, tam)
        if draw.textlength(texto, font=f) <= ancho_max:
            return f
        tam -= 2
    return _fuente(nombre, minimo)


def _abrir(path):
    try:
        if path and os.path.isfile(path):
            return Image.open(path).convert("RGBA")
    except Exception:
        pass
    return None


def generar(d):
    foto = _abrir(d.get("foto_path"))
    if foto:
        fondo = ImageOps.fit(foto.convert("RGB"), (W, H), method=Image.LANCZOS, centering=(0.5, 0.45))
    else:
        fondo = Image.new("RGB", (W, H), NAVY)
    img = fondo.convert("RGBA")

    # Degradé oscuro desde el medio hacia abajo para que el texto se lea.
    deg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = deg.load()
    y0 = 150
    for y in range(y0, H):
        a = int(252 * min(1.0, ((y - y0) / (H - y0 - 120)) ** 0.75))
        for x in range(W):
            px[x, y] = (8, 15, 26, a)
    img = Image.alpha_composite(img, deg)
    dr = ImageDraw.Draw(img)
    _texto_real = dr.text

    def _texto(xy, t, font=None, fill=None):
        _texto_real((xy[0] + 2, xy[1] + 2), t, font=font, fill=(0, 0, 0, 170))
        _texto_real(xy, t, font=font, fill=fill)
    dr.text = _texto

    # Logo de la agencia arriba a la izquierda, sobre una pastilla blanca.
    logo = _abrir(d.get("logo_path"))
    if logo:
        logo.thumbnail((250, 84))
        pw, ph = logo.width + 28, logo.height + 22
        dr.rounded_rectangle((40, 36, 40 + pw, 36 + ph), radius=16, fill=(255, 255, 255, 245))
        img.alpha_composite(logo, (54, 47))

    izq, ancho = 60, W - 120
    # Título y datos
    f_tit = _ajustar(dr, d["titulo"], "Lato-Bold.ttf", 56, ancho)
    dr.text((izq, 318), d["titulo"], font=f_tit, fill=(255, 255, 255))
    if d.get("datos"):
        dr.text((izq, 392), d["datos"], font=_fuente("Lato-Regular.ttf", 30), fill=(190, 200, 214))

    # Precio grande + forma de pago a la derecha
    y_precio = 436
    if d.get("precio"):
        f_pre = _fuente("Lato-Black.ttf", 92)
        dr.text((izq, y_precio), d["precio"], font=f_pre, fill=ORO)
        x_plan = izq + int(dr.textlength(d["precio"], font=f_pre)) + 44
        f_plan = _fuente("Lato-Bold.ttf", 29)
        if d.get("plan_1") and x_plan < W - 260:
            for i, linea in enumerate([d["plan_1"], d.get("plan_2")]):
                if linea:
                    f = _ajustar(dr, linea, "Lato-Bold.ttf", 29, W - 60 - x_plan, 20)
                    dr.text((x_plan, y_precio + 22 + i * 42), linea, font=f, fill=(255, 255, 255))

    # Fila inferior: agencia a la izquierda, «Ver ficha completa» a la derecha
    y_fila = 566
    cta = "Ver ficha completa"
    f_cta = _fuente("Lato-Bold.ttf", 26)
    cw = int(dr.textlength(cta, font=f_cta)) + 48
    dr.rounded_rectangle((W - 60 - cw, y_fila - 8, W - 60, y_fila + 42), radius=25, fill=ORO)
    _texto_real((W - 60 - cw + 24, y_fila + 2), cta, font=f_cta, fill=(26, 20, 5))
    if d.get("agencia"):
        f = _ajustar(dr, d["agencia"], "Lato-Regular.ttf", 27, W - 120 - cw - 30, 20)
        dr.text((izq, y_fila + 3), d["agencia"], font=f, fill=(210, 218, 230))

    out = io.BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=84, optimize=True, progressive=True)
    return out.getvalue()
