"""
Extrae datos de la foto del Título del Automotor (o Cédula de Identificación)
para precargar el alta rápida de un vehículo en Stock (pedido de Daniel
16/09/2026: "cargar cada vehículo tomando una foto del título y de ahí sacar
todos los datos del mismo").

Cómo funciona:
  - OCR local con Tesseract (pytesseract) — elegido en vez de una API de IA
    con visión porque no tiene costo por uso ni depende de una key externa,
    a cambio de ser menos preciso con sellos/fotocopias/manuscrito (decisión
    de Daniel 16/09/2026).
  - El idioma español de Tesseract (`spa.traineddata`) NO viene instalado en
    el sistema por defecto y no se pudo instalar a nivel sistema (sin permisos
    de administrador en este entorno) — por eso se agrupó `spa.traineddata` +
    `eng.traineddata` en la carpeta `tessdata/` de este mismo proyecto y se
    apunta ahí con `--tessdata-dir`, en vez de depender de que el servidor de
    despliegue (Railway) tenga el paquete `tesseract-ocr-spa` del sistema.
    Sigue haciendo falta el binario `tesseract-ocr` instalado en el sistema
    (el motor en sí, no los idiomas).

Qué NO hace (a propósito, mismo criterio "nunca inventes datos" que ya usa
el flujo de marketing de AGENCIA INGRESOS): si un dato no se puede leer con
confianza, se deja afuera del resultado en vez de adivinarlo. Kilometraje y
color nunca se buscan acá porque no están en el título (los carga Daniel a
mano en el mismo formulario, igual que siempre).
"""
import os
import re
import unicodedata

from PIL import Image, ImageOps
import pytesseract

TESSDATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tessdata")
_TESSERACT_CONFIG = f'--tessdata-dir "{TESSDATA_DIR}"' if os.path.isdir(TESSDATA_DIR) else ""
_IDIOMA = "spa+eng" if os.path.isfile(os.path.join(TESSDATA_DIR, "spa.traineddata")) else "eng"

_ANIO_MIN = 1960

# Patente vieja (LLLNNN, ej. ABC123) y patente Mercosur (LLNNNLL, ej. AB123CD).
_RE_DOMINIO_MERCOSUR = re.compile(r"\b([A-Z]{2}\s?\d{3}\s?[A-Z]{2})\b")
_RE_DOMINIO_VIEJO = re.compile(r"\b([A-Z]{3}\s?\d{3})\b")

_RE_ANIO = re.compile(r"\b(19[6-9]\d|20[0-4]\d)\b")


def _buscar_codigo_por_etiqueta(texto_mayus, etiqueta):
    """Busca una línea que empiece con la etiqueta (MOTOR, CHASIS) como
    palabra completa -- así no matchea 'MOTOR' adentro de 'AUTOMOTOR' -- y
    devuelve el código alfanumérico que sigue en esa misma línea, sacando
    conectores típicos (N°, Nro, dos puntos) y espacios sueltos que a veces
    mete el OCR en medio del código. Si lo que queda no parece un código
    real (muy corto/largo, o sin ningún dígito), no devuelve nada -- mejor
    dejarlo en blanco que inventar un código que no es."""
    patron_linea = re.compile(rf"\b{etiqueta}\b\s*(.{{0,40}})")
    m = patron_linea.search(texto_mayus)
    if not m:
        return None
    resto = m.group(1).splitlines()[0] if m.group(1) else ""
    resto = re.sub(r"\b(N|NRO|NUMERO|NO)\b", " ", resto)
    resto = re.sub(r"[°ºÑ:\-]", " ", resto)
    codigo = re.sub(r"[^A-Z0-9]", "", resto)
    if 5 <= len(codigo) <= 20 and any(c.isdigit() for c in codigo):
        return codigo
    return None


def _quitar_tildes(txt):
    return "".join(c for c in unicodedata.normalize("NFKD", txt) if not unicodedata.combining(c))


def _preprocesar(imagen_bytes):
    """Escala de grises + autocontraste + upscale si la foto es chica --
    mejora bastante la lectura de fotos sacadas con el celular en mano,
    sin necesitar nada más pesado que Pillow."""
    from io import BytesIO

    img = Image.open(BytesIO(imagen_bytes))
    img = img.convert("L")
    img = ImageOps.autocontrast(img)
    if img.width < 1600:
        factor = 1600 / img.width
        img = img.resize((int(img.width * factor), int(img.height * factor)), Image.LANCZOS)
    return img


def _texto_ocr(imagen_bytes):
    img = _preprocesar(imagen_bytes)
    return pytesseract.image_to_string(img, lang=_IDIOMA, config=_TESSERACT_CONFIG)


def _buscar_dominio(texto_mayus):
    m = _RE_DOMINIO_MERCOSUR.search(texto_mayus)
    if m:
        return re.sub(r"\s", "", m.group(1))
    m = _RE_DOMINIO_VIEJO.search(texto_mayus)
    if m:
        return re.sub(r"\s", "", m.group(1))
    return None


def _buscar_marca(texto_mayus, marcas_conocidas):
    """Busca, entre las marcas ya usadas en la app (obtener_catalogo), cuál
    aparece tal cual en el texto leído -- más confiable que tratar de
    'adivinar' una etiqueta MARCA en un formato de título que varía."""
    texto_sin_tildes = _quitar_tildes(texto_mayus)
    for marca in sorted(marcas_conocidas, key=len, reverse=True):
        if not marca:
            continue
        marca_norm = _quitar_tildes(marca.upper())
        if re.search(rf"\b{re.escape(marca_norm)}\b", texto_sin_tildes):
            return marca
    return None


def _buscar_modelo(texto_mayus, marca, modelos_conocidos):
    """Igual criterio que la marca: solo devuelve un modelo si aparece tal
    cual entre los modelos ya cargados en la app para esa marca."""
    if not marca:
        return None
    texto_sin_tildes = _quitar_tildes(texto_mayus)
    for modelo in sorted(modelos_conocidos, key=len, reverse=True):
        if not modelo:
            continue
        modelo_norm = _quitar_tildes(modelo.upper())
        if len(modelo_norm) >= 3 and re.search(rf"\b{re.escape(modelo_norm)}\b", texto_sin_tildes):
            return modelo
    return None


def extraer_datos_titulo(imagen_bytes, catalogo=None):
    """catalogo: el dict {marca: {modelo: {...}}} de database.obtener_catalogo(),
    para reconocer marca/modelo solo si coinciden con algo ya cargado en la
    app (evita inventar una marca/modelo que Tesseract leyó mal).

    Devuelve {"marca", "modelo", "anio", "dominio", "motor", "chasis",
    "reconocidos": [...], "texto_ocr": str} -- los campos no reconocidos
    quedan en None, nunca con un valor adivinado.
    """
    catalogo = catalogo or {}
    texto = _texto_ocr(imagen_bytes)
    texto_mayus = texto.upper()

    marca = _buscar_marca(texto_mayus, catalogo.keys())
    modelos_de_marca = list(catalogo.get(marca, {}).keys()) if marca else []
    modelo = _buscar_modelo(texto_mayus, marca, modelos_de_marca)

    dominio = _buscar_dominio(texto_mayus)

    anios_encontrados = _RE_ANIO.findall(texto_mayus)
    anio = int(anios_encontrados[0]) if anios_encontrados else None

    motor = _buscar_codigo_por_etiqueta(texto_mayus, "MOTOR")
    chasis = _buscar_codigo_por_etiqueta(texto_mayus, "CHASIS")

    datos = {"marca": marca, "modelo": modelo, "anio": anio, "dominio": dominio, "motor": motor, "chasis": chasis}
    reconocidos = [campo for campo, valor in datos.items() if valor]
    datos["reconocidos"] = reconocidos
    datos["texto_ocr"] = texto
    return datos
