"""
Parsea el informe de estrategia en Markdown que hoy entrega AGENCIA INGRESOS
(otro proyecto de Cowork, conversacional) en bloques por sección (## ...) y
subsección (### ...), cada uno con su HTML ya renderizado -- para que la
sección Marketing de esta app lo muestre prolijo y con un botón "Copiar" por
bloque, en vez de un textarea de markdown crudo (pedido de Daniel
17/09/2026: guardar/organizar lo que ya genera ese chat, sin IA propia
todavía).

El botón de copiar en el template usa `.innerText` del HTML ya renderizado
(no el markdown crudo) -- así lo que se pega en Facebook/Marketplace es
texto plano de verdad, sin `**`, `>` ni `#` de markdown de por medio.
"""
import re

import markdown as _markdown_lib

_RE_H1 = re.compile(r"^#\s+(.*)")
_RE_H2 = re.compile(r"^##\s+(?!#)(.*)")
_RE_H3 = re.compile(r"^###\s+(.*)")


def _render(lineas):
    texto = "\n".join(lineas).strip()
    if not texto:
        return ""
    return _markdown_lib.markdown(texto, extensions=["tables"])


def parsear(md_texto):
    """Devuelve {"titulo": str|None, "encabezado_html": str,
    "bloques": [{"titulo", "html", "hijos": [{"titulo","html"}, ...]}]}."""
    lineas = (md_texto or "").replace("\r\n", "\n").split("\n")

    titulo = None
    encabezado = []
    bloques = []
    actual = None
    i = 0

    if lineas and _RE_H1.match(lineas[0] or ""):
        titulo = _RE_H1.match(lineas[0]).group(1).strip()
        i = 1

    for linea in lineas[i:]:
        m2 = _RE_H2.match(linea)
        m3 = _RE_H3.match(linea)
        if m2:
            if actual:
                bloques.append(actual)
            actual = {"titulo": m2.group(1).strip(), "lineas": [], "hijos": []}
        elif m3 and actual is not None:
            actual["hijos"].append({"titulo": m3.group(1).strip(), "lineas": []})
        elif actual is None:
            encabezado.append(linea)
        else:
            destino = actual["hijos"][-1]["lineas"] if actual["hijos"] else actual["lineas"]
            destino.append(linea)

    if actual:
        bloques.append(actual)

    resultado_bloques = []
    for b in bloques:
        resultado_bloques.append({
            "titulo": b["titulo"],
            "html": _render(b["lineas"]),
            "hijos": [{"titulo": h["titulo"], "html": _render(h["lineas"])} for h in b["hijos"]],
        })

    return {
        "titulo": titulo,
        "encabezado_html": _render(encabezado),
        "bloques": resultado_bloques,
    }
