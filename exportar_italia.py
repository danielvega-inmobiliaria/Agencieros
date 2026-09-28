"""Exporta los datos reales de Italia Automotores (agencia 1) de la base
local (data/agencieros.db) a seed/italia/ -- 28/09/2026.

La web arrancó el 18/09 con una base nueva y ahí Italia tenía solo los
autos de ejemplo del seed. Este export + la migración
`_importar_italia_real` de database.py pasan a la web los autos, fotos,
pedidos, tomas/tasaciones y financiaciones cargados en la compu de Daniel.
"""
import json, os, shutil, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
DESTINO = os.path.join(BASE, "seed", "italia")
TABLAS = ["vehiculos", "vehiculo_fotos", "pedidos_clientes", "tomas_vehiculo",
          "inspeccion_visual", "inspeccion_marcadores", "tasaciones",
          "financiaciones", "financiacion_cuotas", "garantes", "ventas", "agencia_config"]

c = sqlite3.connect(os.path.join(BASE, "data", "agencieros.db"))
c.row_factory = sqlite3.Row
def filas(sql, params=()):
    return [dict(r) for r in c.execute(sql, params)]

datos = {}
datos["vehiculos"] = filas("SELECT * FROM vehiculos WHERE COALESCE(agencia_id,1)=1")
vids = [v["id"] for v in datos["vehiculos"]] or [-1]
q = ",".join("?" * len(vids))
datos["vehiculo_fotos"] = filas(f"SELECT * FROM vehiculo_fotos WHERE vehiculo_id IN ({q})", vids)
datos["pedidos_clientes"] = filas("SELECT * FROM pedidos_clientes WHERE COALESCE(agencia_id,1)=1")
datos["tomas_vehiculo"] = filas("SELECT * FROM tomas_vehiculo WHERE COALESCE(agencia_id,1)=1")
tids = [t["id"] for t in datos["tomas_vehiculo"]] or [-1]
q = ",".join("?" * len(tids))
datos["inspeccion_visual"] = filas(f"SELECT * FROM inspeccion_visual WHERE toma_id IN ({q})", tids)
iids = [i["id"] for i in datos["inspeccion_visual"]] or [-1]
q = ",".join("?" * len(iids))
datos["inspeccion_marcadores"] = filas(f"SELECT * FROM inspeccion_marcadores WHERE inspeccion_visual_id IN ({q})", iids)
datos["tasaciones"] = filas("SELECT * FROM tasaciones WHERE COALESCE(agencia_id,1)=1")
datos["financiaciones"] = filas("SELECT * FROM financiaciones WHERE COALESCE(agencia_id,1)=1")
fids = [f["id"] for f in datos["financiaciones"]] or [-1]
q = ",".join("?" * len(fids))
datos["financiacion_cuotas"] = filas(f"SELECT * FROM financiacion_cuotas WHERE financiacion_id IN ({q})", fids)
datos["garantes"] = filas(f"SELECT * FROM garantes WHERE financiacion_id IN ({q})", fids)
datos["ventas"] = filas("SELECT * FROM ventas WHERE COALESCE(agencia_id,1)=1")
datos["agencia_config"] = filas("SELECT * FROM agencia_config WHERE agencia_id=1")

# Archivos subidos que usan esas filas
urls = set()
for t in datos.values():
    for fila in t:
        for k, v in fila.items():
            if isinstance(v, str) and v.startswith("/static/uploads/"):
                urls.add(v)
if os.path.isdir(DESTINO):
    shutil.rmtree(DESTINO)
faltan = []
for u in sorted(urls):
    rel = u[len("/static/uploads/"):]
    src = os.path.join(BASE, "static", "uploads", rel)
    if not os.path.exists(src):
        faltan.append(u); continue
    dst = os.path.join(DESTINO, "uploads", rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
os.makedirs(DESTINO, exist_ok=True)
with open(os.path.join(DESTINO, "italia.json"), "w", encoding="utf-8") as f:
    json.dump(datos, f, ensure_ascii=False, indent=1)
print({k: len(v) for k, v in datos.items()}, "archivos:", len(urls) - len(faltan), "faltan:", faltan)
