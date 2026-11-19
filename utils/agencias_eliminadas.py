"""Archivo de agencias eliminadas a mano (19/11/2026).

Antes de borrar una agencia desde el Panel se guarda una copia completa
(la fila de `agencias` y todas las filas de cualquier tabla con `agencia_id`)
como JSON en la tabla `agencias_eliminadas`. Sirve para restaurarla si la
persona quiere volver, o para descargar el JSON. Railway no tiene copias de
seguridad del volumen, así que este archivo es la única red de seguridad.

Límites: guarda lo que está en la base SQLite; las imágenes que estén en
disco (fuera de la base) no se copian. La copia vive en el mismo volumen que
la base: protege de un borrado por error, no de perder el volumen entero.
"""
import base64
import json
from datetime import datetime

from database import get_db


def asegurar_tabla():
    db = get_db()
    db.execute(
        """CREATE TABLE IF NOT EXISTS agencias_eliminadas (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               agencia_id INTEGER,
               nombre TEXT,
               email TEXT,
               telefono TEXT,
               validada INTEGER DEFAULT 0,
               filas INTEGER DEFAULT 0,
               eliminada_at TEXT,
               restaurada INTEGER DEFAULT 0,
               datos TEXT
           )"""
    )
    db.commit()


def _val(v):
    if isinstance(v, (bytes, bytearray)):
        return {"__b64__": base64.b64encode(bytes(v)).decode("ascii")}
    return v


def _unval(v):
    if isinstance(v, dict) and "__b64__" in v:
        return base64.b64decode(v["__b64__"])
    return v


def archivar(agencia_id):
    """Guarda la copia. Devuelve el id del archivo o None si no pudo (en ese
    caso NO hay que borrar la agencia). No hace commit del borrado."""
    asegurar_tabla()
    db = get_db()
    ag = db.execute("SELECT * FROM agencias WHERE id = ?", (agencia_id,)).fetchone()
    if ag is None:
        return None
    datos = {"agencias": [{k: _val(ag[k]) for k in ag.keys()}]}
    total = 1
    for (t,) in db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall():
        if t in ("agencias", "agencias_eliminadas"):
            continue
        cols = [c[1] for c in db.execute(f'PRAGMA table_info("{t}")').fetchall()]
        if "agencia_id" not in cols:
            continue
        filas = db.execute(f'SELECT * FROM "{t}" WHERE agencia_id = ?', (agencia_id,)).fetchall()
        if filas:
            datos[t] = [{k: _val(f[k]) for k in f.keys()} for f in filas]
            total += len(filas)
    cur = db.execute(
        """INSERT INTO agencias_eliminadas
           (agencia_id, nombre, email, telefono, validada, filas, eliminada_at, datos)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (agencia_id, ag["nombre_agencia"], ag["email"], ag["telefono"],
         1 if ag["email_verificado"] else 0, total,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), json.dumps(datos, ensure_ascii=False)),
    )
    db.commit()
    return cur.lastrowid


def restaurar(archivo_id):
    """Vuelve a cargar la agencia con sus ids originales (las claves son
    AUTOINCREMENT: no se reutilizan). Devuelve (ok, mensaje)."""
    asegurar_tabla()
    db = get_db()
    reg = db.execute("SELECT * FROM agencias_eliminadas WHERE id = ?", (archivo_id,)).fetchone()
    if reg is None:
        return False, "No existe esa copia."
    if reg["restaurada"]:
        return False, "Esa agencia ya se restauró."
    datos = json.loads(reg["datos"])
    ag = datos["agencias"][0]
    if db.execute("SELECT 1 FROM agencias WHERE id = ? OR LOWER(email) = LOWER(?)",
                  (ag["id"], ag.get("email") or "")).fetchone():
        return False, "Ya hay una agencia con ese id o ese mail: no se pisa."
    try:
        db.commit()
        db.execute("PRAGMA foreign_keys = OFF")
        db.execute("BEGIN")
        for tabla in ["agencias"] + [t for t in datos if t != "agencias"]:
            cols_db = {c[1] for c in db.execute(f'PRAGMA table_info("{tabla}")').fetchall()}
            for fila in datos[tabla]:
                cols = [c for c in fila if c in cols_db]
                db.execute(
                    f'INSERT INTO "{tabla}" ({",".join(chr(34) + c + chr(34) for c in cols)}) '
                    f'VALUES ({",".join("?" * len(cols))})',
                    [_unval(fila[c]) for c in cols],
                )
        db.execute("UPDATE agencias_eliminadas SET restaurada = 1 WHERE id = ?", (archivo_id,))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[agencias_eliminadas] no se pudo restaurar {archivo_id}: {e}", flush=True)
        return False, f"No se pudo restaurar: {e}"
    finally:
        db.execute("PRAGMA foreign_keys = ON")
    return True, "Agencia restaurada con todos sus datos."
