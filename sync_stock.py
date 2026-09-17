"""
Sincroniza los vehículos cargados en 03_AUTOMOTOR/STOCK (una carpeta por
vehículo, con la ficha HTML que genera el flujo de marketing) hacia la
tabla `vehiculos` de la app AGENCIEROS.

Cómo se dispara:
  - A mano: `python sync_stock.py` parado en la carpeta APP_AGENCIEROS.
  - Desde la app: botón "Sincronizar desde STOCK" en el módulo Stock
    (routes/stock.py llama a sync_stock()).

Qué hace:
  - Recorre cada subcarpeta de STOCK/, busca su Ficha_*.html (ignora las
    que digan "Demo" en el nombre) y extrae: marca, modelo, versión, año,
    km, combustible, transmisión, ubicación, estado general, condiciones
    de pago, precio publicado y equipamiento.
  - Si la carpeta ya se había sincronizado antes (se matchea por nombre de
    carpeta, guardado en la columna `carpeta_stock`), ACTUALIZA esos datos
    comerciales pero nunca toca lo que se cargó a mano en la app: valor de
    compra, gastos, estado (disponible / por ingresar / en reparación /
    vendido) ni valor/fecha de venta.
  - Si es una carpeta nueva, la inserta en Stock con estado "disponible".
  - Si es una carpeta nueva pero ya existe un vehículo cargado a mano con
    la misma marca/modelo/año y todavía sin carpeta vinculada (por ejemplo,
    uno cargado por foto del título antes de tener su ficha en STOCK/), lo
    vincula a esa carpeta en vez de crear un duplicado -- completando solo
    los datos que estén vacíos, sin pisar marca/modelo/versión/dominio que
    Daniel ya cargó a mano (agregado 17/09/2026, después de que la primera
    sincronización real duplicara Fiat ARGO y Peugeot 408 que ya estaban
    cargados).

Qué NO hace (todavía):
  - No trae las fotos incrustadas en la ficha — eso se conecta más
    adelante, cuando se actualice esa parte del proyecto (ver PROYECTO.md).
  - No borra de Stock un vehículo si se borra su carpeta en STOCK/ (evita
    perder historial/datos económicos cargados a mano por accidente).
"""
import os
import re
import sqlite3
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import DB_PATH, init_db  # noqa: E402

STOCK_DIR = os.environ.get(
    "STOCK_DIR",
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "STOCK")),
)

_ROW_RE = re.compile(
    r'<span class="info-label">(.*?)</span>\s*<span class="info-value">(.*?)</span>',
    re.DOTALL,
)
_CHIP_RE = re.compile(r'<span class="equip-chip">(.*?)</span>', re.DOTALL)
_BADGE_RE = re.compile(r'<span class="badge">(.*?)</span>', re.DOTALL)
_PRICE_RE = re.compile(r'<div class="price">(.*?)</div>', re.DOTALL)
_PRICE_NOTE_RE = re.compile(r'<div class="price-note">(.*?)</div>', re.DOTALL)


def _clean(txt):
    return re.sub(r"\s+", " ", txt or "").strip()


def _a_numero(txt):
    """'$ 16.000.000' o '90.683 km' -> 16000000 / 90683"""
    if not txt:
        return None
    digitos = re.sub(r"[^\d]", "", txt)
    return int(digitos) if digitos else None


def _encontrar_ficha(carpeta):
    candidatos = [
        f for f in os.listdir(carpeta)
        if f.lower().startswith("ficha_")
        and f.lower().endswith(".html")
        and "demo" not in f.lower()
    ]
    if not candidatos:
        return None
    return os.path.join(carpeta, sorted(candidatos)[0])


def _parsear_ficha(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()

    info = {_clean(k).lower(): _clean(v) for k, v in _ROW_RE.findall(html)}
    equipamiento = ", ".join(_clean(c) for c in _CHIP_RE.findall(html))
    badge_m = _BADGE_RE.search(html)
    price_m = _PRICE_RE.search(html)
    note_m = _PRICE_NOTE_RE.search(html)

    marca_modelo = info.get("marca / modelo", "")
    partes = marca_modelo.split(" ", 2)
    marca = partes[0] if len(partes) > 0 and partes[0] else None
    modelo = partes[1] if len(partes) > 1 else None
    version = partes[2] if len(partes) > 2 else None

    estado_badge = _clean(badge_m.group(1)) if badge_m else ""
    estado_sugerido = "vendido" if estado_badge.lower() == "vendido" else "disponible"

    return {
        "marca": marca,
        "modelo": modelo,
        "version": version,
        "anio": _a_numero(info.get("año")),
        "km": _a_numero(info.get("kilometraje")),
        "combustible": info.get("combustible"),
        "caja": info.get("transmisión"),
        "dominio": info.get("dominio"),
        "estado_general": info.get("estado general"),
        "ubicacion": info.get("ubicación"),
        "condiciones_pago": _clean(note_m.group(1)) if note_m else None,
        "valor_publicado": _a_numero(price_m.group(1)) if price_m else None,
        "equipamiento": equipamiento or None,
        "estado_sugerido": estado_sugerido,
    }


def sync_stock(stock_dir=None, db_path=None):
    """Corre la sincronización. Devuelve un dict con el resumen:
    {"nuevos": [...], "actualizados": [...], "sin_ficha": [...], "error": str|None}
    """
    stock_dir = stock_dir or STOCK_DIR
    resultado = {"nuevos": [], "actualizados": [], "vinculados": [], "sin_ficha": [], "error": None}

    if not os.path.isdir(stock_dir):
        resultado["error"] = f"No encuentro la carpeta STOCK en: {stock_dir}"
        return resultado

    init_db()  # asegura que la tabla vehiculos tenga las columnas nuevas
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        for carpeta_nombre in sorted(os.listdir(stock_dir)):
            carpeta_path = os.path.join(stock_dir, carpeta_nombre)
            if not os.path.isdir(carpeta_path):
                continue

            ficha_path = _encontrar_ficha(carpeta_path)
            if not ficha_path:
                resultado["sin_ficha"].append(carpeta_nombre)
                continue

            datos = _parsear_ficha(ficha_path)
            existente = conn.execute(
                "SELECT id FROM vehiculos WHERE carpeta_stock = ?", (carpeta_nombre,)
            ).fetchone()

            vinculado_ahora = False
            if not existente and datos["marca"] and datos["modelo"] and datos["anio"]:
                candidato = conn.execute(
                    """SELECT * FROM vehiculos
                       WHERE carpeta_stock IS NULL
                         AND LOWER(marca) = LOWER(?) AND LOWER(modelo) = LOWER(?) AND anio = ?
                       ORDER BY id LIMIT 1""",
                    (datos["marca"], datos["modelo"], datos["anio"]),
                ).fetchone()
                if candidato:
                    # Ya estaba cargado a mano (ej. por foto del título) -- se
                    # vincula a esta carpeta en vez de crear un duplicado.
                    # Solo se completan los campos que están vacíos; nunca se
                    # pisa lo que Daniel ya cargó a mano.
                    conn.execute(
                        """UPDATE vehiculos SET
                             carpeta_stock = ?,
                             km = COALESCE(km, ?),
                             combustible = COALESCE(combustible, ?),
                             caja = COALESCE(caja, ?),
                             ubicacion = COALESCE(ubicacion, ?),
                             condiciones_pago = COALESCE(condiciones_pago, ?),
                             estado_general = COALESCE(estado_general, ?),
                             equipamiento = COALESCE(equipamiento, ?),
                             valor_publicado = CASE WHEN valor_publicado IS NULL OR valor_publicado = 0
                                                     THEN ? ELSE valor_publicado END,
                             updated_at = datetime('now')
                           WHERE id = ?""",
                        (
                            carpeta_nombre, datos["km"], datos["combustible"], datos["caja"],
                            datos["ubicacion"], datos["condiciones_pago"], datos["estado_general"],
                            datos["equipamiento"], datos["valor_publicado"], candidato["id"],
                        ),
                    )
                    resultado.setdefault("vinculados", []).append(carpeta_nombre)
                    vinculado_ahora = True

            if vinculado_ahora:
                pass
            elif existente:
                conn.execute(
                    """UPDATE vehiculos SET
                         marca=?, modelo=?, version=?, anio=?, km=?, combustible=?, caja=?,
                         dominio=COALESCE(?, dominio), ubicacion=?, condiciones_pago=?,
                         estado_general=?, equipamiento=?, valor_publicado=?,
                         updated_at=datetime('now')
                       WHERE id=?""",
                    (
                        datos["marca"], datos["modelo"], datos["version"], datos["anio"],
                        datos["km"], datos["combustible"], datos["caja"], datos["dominio"],
                        datos["ubicacion"], datos["condiciones_pago"], datos["estado_general"],
                        datos["equipamiento"], datos["valor_publicado"], existente["id"],
                    ),
                )
                resultado["actualizados"].append(carpeta_nombre)
            else:
                conn.execute(
                    """INSERT INTO vehiculos
                       (marca, modelo, version, anio, km, combustible, caja, dominio, estado,
                        ubicacion, condiciones_pago, estado_general, equipamiento,
                        valor_compra, gastos, valor_publicado, fecha_ingreso, carpeta_stock)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        datos["marca"], datos["modelo"], datos["version"], datos["anio"],
                        datos["km"], datos["combustible"], datos["caja"], datos["dominio"],
                        datos["estado_sugerido"], datos["ubicacion"], datos["condiciones_pago"],
                        datos["estado_general"], datos["equipamiento"], 0, 0,
                        datos["valor_publicado"] or 0, str(date.today()), carpeta_nombre,
                    ),
                )
                resultado["nuevos"].append(carpeta_nombre)

        conn.commit()
    finally:
        conn.close()

    return resultado


if __name__ == "__main__":
    r = sync_stock()
    if r["error"]:
        print("No se pudo sincronizar:", r["error"])
    else:
        print(f"Nuevos: {len(r['nuevos'])} {r['nuevos']}")
        print(f"Vinculados a uno ya cargado a mano: {len(r['vinculados'])} {r['vinculados']}")
        print(f"Actualizados: {len(r['actualizados'])} {r['actualizados']}")
        if r["sin_ficha"]:
            print(f"Carpetas sin ficha (ignoradas): {r['sin_ficha']}")
