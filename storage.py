"""Rutas de almacenamiento persistente: base de datos y archivos subidos
(fotos de stock, fotos de inspeccion, logo de agencia) -- 18/09/2026,
preparando el deploy a Railway.

Railway permite UN solo volumen persistente por servicio, montado en el
path que indica la variable de entorno RAILWAY_VOLUME_MOUNT_PATH (ej.
"/data"). Como la base SQLite y las fotos subidas necesitan sobrevivir
a cada redeploy, las dos comparten ese mismo volumen (en subcarpetas
separadas: <volumen>/agencieros.db y <volumen>/uploads/...).

En local (sin esa variable, como en la compu de Daniel) todo sigue
funcionando exactamente igual que siempre: la base en data/agencieros.db
y las fotos en static/uploads/, relativas a la carpeta del proyecto -- no
hace falta ningun volumen para seguir desarrollando en local.
"""
import os

VOLUME_DIR = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def db_path():
    if VOLUME_DIR:
        return os.path.join(VOLUME_DIR, "agencieros.db")
    return os.path.join(_BASE_DIR, "data", "agencieros.db")


def uploads_dir(*parts):
    """Carpeta fisica donde se guardan/leen los archivos subidos. Las URLs
    que se guardan en la base (`/static/uploads/...`) no cambian -- en
    app.py hay una ruta que intercepta ese prefijo y sirve los archivos
    desde aca, sea el volumen de Railway o la carpeta local de siempre."""
    if VOLUME_DIR:
        base = os.path.join(VOLUME_DIR, "uploads")
    else:
        base = os.path.join(_BASE_DIR, "static", "uploads")
    return os.path.join(base, *parts)
