"""Envío de vehículos del stock a la Red de Promotores (app aparte, API con token).

Variables de entorno (Railway de Agencieros):
  RED_PROMOTORES_URL          https://red-promotores-production.up.railway.app
  RED_PROMOTORES_TOKEN        mismo valor que IMPORT_TOKEN en Red de Promotores
  RED_PROMOTORES_SLUG         slug del comercio en Red de Promotores (default: italia)
  RED_PROMOTORES_AGENCIA_ID   id de la agencia de Agencieros que usa la función
                              (default: STOCK_SYNC_AGENCIA_ID o 1 = Italia)
Sin URL o sin token el botón no aparece.

Sincronización automática: una vez compartida una unidad (vehiculos.red_promotores = 1),
cualquier cambio de precio, fotos, costos o estado se reenvía solo (en segundo plano).
Si deja de estar disponible (señada, vendida, etc.) se quita de la Red; si vuelve a
disponible, reaparece.
"""
import json
import os
import threading
import urllib.error
import urllib.request

from flask import g


def _agencia_id():
    return int(os.environ.get("RED_PROMOTORES_AGENCIA_ID") or os.environ.get("STOCK_SYNC_AGENCIA_ID") or "1")


def habilitado(agencia_id):
    return bool(os.environ.get("RED_PROMOTORES_URL") and os.environ.get("RED_PROMOTORES_TOKEN")) and agencia_id == _agencia_id()


def enviar(payload):
    """POST a /api/vehiculos/sync. Devuelve (ok, mensaje)."""
    base = os.environ["RED_PROMOTORES_URL"].rstrip("/")
    payload = dict(payload, comercio_slug=os.environ.get("RED_PROMOTORES_SLUG", "italia"))
    req = urllib.request.Request(
        base + "/api/vehiculos/sync",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + os.environ["RED_PROMOTORES_TOKEN"], "Content-Type": "application/json",
                 "User-Agent": "agencieros/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return True, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        return False, "Red de Promotores respondió %s" % e.code
    except Exception as e:
        return False, "No se pudo conectar con Red de Promotores (%s)" % type(e).__name__


def marcar(vehiculo_id):
    """Anota la unidad para reenviarla a la Red al terminar el request (si está compartida)."""
    try:
        g.setdefault("red_promotores_pendientes", set()).add(int(vehiculo_id))
    except (RuntimeError, TypeError, ValueError):
        pass


def enviar_en_segundo_plano(payload):
    """Envía sin demorar la pantalla del usuario (la Red descarga las fotos y puede tardar)."""
    def _trabajo():
        ok, r = enviar(payload)
        if not ok:
            print("[red_promotores] sync %s: %s" % (payload.get("ref_externa"), r), flush=True)
    threading.Thread(target=_trabajo, daemon=True).start()
