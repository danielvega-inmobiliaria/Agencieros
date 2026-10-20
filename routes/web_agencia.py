"""Web propia de cada agencia (19/10/2026, pedido de Daniel):
agencieros.net.ar/a/<nombre-agencia> -- una página pública con todo el stock
DISPONIBLE de la agencia, siempre al día porque lee directo de Stock.

Reglas de privacidad: solo se publican datos de cara al comprador (marca,
modelo, versión, año, km, combustible, caja, precio publicado y fotos).
Nunca costo, gastos, ganancia ni consignante. La agencia tiene que activarla
(opt-in) y puede ocultar autos puntuales desde "Mi web".

Dos rutas:
- GET /a/<slug>        pública (sin login), también en el dominio raíz.
- GET/POST /mi-web     la agencia activa su web, elige el nombre del link y
                       marca qué autos se muestran.
"""
import os
import re
import unicodedata
from urllib.parse import quote_plus

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort, jsonify

from database import query, execute, foto_principal, obtener_config_agencia

bp = Blueprint("web_agencia", __name__)

LANDING_URL = os.environ.get("LANDING_URL", "https://agencieros.net.ar").rstrip("/")
APP_URL = os.environ.get("APP_URL", "https://app.agencieros.net.ar").rstrip("/")
RESERVADOS = {"admin", "api", "app", "www", "demo", "configurar", "static", "agencieros"}


def slugify(texto):
    t = unicodedata.normalize("NFKD", str(texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40]


def _slug_valido(slug):
    return bool(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug or "")) and 3 <= len(slug) <= 40 and slug not in RESERVADOS


COLOR_DEFECTO = "#1f4fa8"
MAX_DESTACADOS = 6


def color_valido(c):
    return c if re.fullmatch(r"#[0-9a-fA-F]{6}", c or "") else COLOR_DEFECTO


def _texto_sobre(color):
    """Blanco u oscuro según el brillo del color de acento."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#ffffff" if (0.299 * r + 0.587 * g + 0.114 * b) < 160 else "#111827"


def _pesos(n):
    return "$" + "{:,.0f}".format(n or 0).replace(",", ".")


def _items(agencia_id, slug):
    """Autos a mostrar: disponibles y no ocultados, con solo datos públicos."""
    filas = query(
        """SELECT id, marca, modelo, version, anio, km, combustible, caja, valor_publicado, tipo_carroceria,
                  COALESCE(web_ocultar_precio, 0) AS ocultar_precio, COALESCE(web_destacado, 0) AS destacado
           FROM vehiculos
           WHERE agencia_id = ? AND estado = 'disponible' AND COALESCE(web_visible, 1) = 1
           ORDER BY id DESC""", (agencia_id,))
    items = []
    for v in filas:
        titulo = " ".join(str(x) for x in [v["marca"], v["modelo"]] if x)
        items.append({
            "id": v["id"], "titulo": titulo, "modelo": v["modelo"] or "", "version": v["version"] or "", "marca": v["marca"] or "",
            "anio": v["anio"], "km": v["km"],
            "km_txt": f"{int(v['km']):,} km".replace(",", ".") if v["km"] else "",
            "combustible": v["combustible"] or "", "caja": v["caja"] or "",
            "precio": 0 if v["ocultar_precio"] else (v["valor_publicado"] or 0),
            "precio_txt": _pesos(v["valor_publicado"]) if (v["valor_publicado"] and not v["ocultar_precio"]) else "Consultar",
            "foto": foto_principal(v["id"]), "destacado": bool(v["destacado"]),
            "ficha": f"{APP_URL}/stock/{v['id']}/ficha?wa=0&web={slug}",
        })
    return items


@bp.route("/a/<slug>")
def pagina(slug):
    from routes.stock import _whatsapp_ar, _redes_ordenadas
    ag = query("SELECT id, nombre_agencia, activo, web_activa, web_color FROM agencias WHERE web_slug = ?",
               (slug.lower(),), one=True)
    if not ag or ag["activo"] == 0:
        abort(404)
    es_dueno = session.get("agencia_id") == ag["id"]
    if not ag["web_activa"] and not es_dueno:
        abort(404)
    cfg = _redes_ordenadas(dict(obtener_config_agencia(ag["id"])))
    nombre = cfg.get("nombre_agencia") or ag["nombre_agencia"]
    items = _items(ag["id"], slug.lower())
    numero = _whatsapp_ar(cfg.get("telefono"))
    wa_base = f"https://wa.me/{numero}" if numero else None
    for it in items:
        if wa_base:
            msg = f"Hola! Te escribo por el {it['titulo']} {it['version']} ({it['anio'] or 's/d'}) que vi en tu web."
            it["wa"] = f"{wa_base}?text={quote_plus(msg)}"
    lugar = ", ".join(x for x in [cfg.get("ciudad"), cfg.get("provincia")] if x)
    og_img = items[0]["foto"] if items else cfg.get("logo_url")
    if og_img and og_img.startswith("/"):
        og_img = APP_URL + og_img
    return render_template(
        "web_agencia/pagina.html", nombre=nombre, cfg=cfg, lugar=lugar, items=items,
        marcas=sorted({i["marca"] for i in items if i["marca"]}),
        wa_general=(f"{wa_base}?text={quote_plus('Hola! Vi tu web y quiero consultar por un auto.')}" if wa_base else None),
        url_canonica=f"{LANDING_URL}/a/{slug.lower()}", og_img=og_img,
        destacados=[i for i in items if i["destacado"]][:MAX_DESTACADOS], slug=slug.lower(),
        wa_compramos=(f"{wa_base}?text={quote_plus('Hola! Quiero vender mi auto, vi que lo compran en tu web.')}" if wa_base else None),
        color=color_valido(ag["web_color"]), color_txt=_texto_sobre(color_valido(ag["web_color"])),
        vista_previa=(es_dueno and not ag["web_activa"]), activa=bool(ag["web_activa"]),
    )


@bp.route("/mi-web", methods=["GET", "POST"])
def config():
    agencia_id = session.get("agencia_id")
    if not agencia_id:
        flash("Entrá con la cuenta de una agencia para configurar su web.", "error")
        return redirect(url_for("precios.index"))
    ag = query("SELECT id, nombre_agencia, web_slug, web_activa, web_color FROM agencias WHERE id = ?", (agencia_id,), one=True)
    cfg = obtener_config_agencia(agencia_id)
    sugerido = slugify(cfg.get("nombre_agencia") or ag["nombre_agencia"])
    if request.method == "POST":
        from utils.demo import _es_demo
        if _es_demo(agencia_id):
            flash("En la demo no se puede publicar una web.", "error")
            return redirect(url_for("web_agencia.config"))
        slug = slugify(request.form.get("slug"))
        activa = 1 if request.form.get("activa") else 0
        if not _slug_valido(slug):
            flash("El nombre del link tiene que tener entre 3 y 40 letras o números (se pueden usar guiones), y no ser una palabra reservada.", "error")
            return redirect(url_for("web_agencia.config"))
        otro = query("SELECT id FROM agencias WHERE web_slug = ? AND id <> ?", (slug, agencia_id), one=True)
        if otro:
            flash("Ese nombre de link ya lo usa otra agencia. Probá con otro.", "error")
            return redirect(url_for("web_agencia.config"))
        if activa and not (cfg.get("telefono") or "").strip():
            flash("Antes de activar la web cargá tu WhatsApp comercial en Admin: es el botón para que te consulten.", "error")
            return redirect(url_for("web_agencia.config"))
        color = color_valido(request.form.get("color"))
        execute("UPDATE agencias SET web_slug = ?, web_activa = ?, web_color = ? WHERE id = ?", (slug, activa, color, agencia_id))
        visibles = {int(x) for x in request.form.getlist("visible") if x.isdigit()}
        sin_precio = {int(x) for x in request.form.getlist("sin_precio") if x.isdigit()}
        destacados = [int(x) for x in request.form.getlist("destacado") if x.isdigit()][:MAX_DESTACADOS]
        for v in query("SELECT id FROM vehiculos WHERE agencia_id = ? AND estado = 'disponible'", (agencia_id,)):
            execute("UPDATE vehiculos SET web_visible = ?, web_ocultar_precio = ?, web_destacado = ? WHERE id = ?",
                    (1 if v["id"] in visibles else 0, 1 if v["id"] in sin_precio else 0,
                     1 if v["id"] in destacados else 0, v["id"]))
        flash("Web guardada." + (" Ya está publicada." if activa else " Todavía está oculta al público."), "success")
        return redirect(url_for("web_agencia.config"))
    vehiculos = [dict(v, foto=foto_principal(v["id"])) for v in query(
        """SELECT id, marca, modelo, version, anio, valor_publicado, COALESCE(web_visible, 1) AS web_visible,
                  COALESCE(web_ocultar_precio, 0) AS ocultar_precio, COALESCE(web_destacado, 0) AS destacado
           FROM vehiculos WHERE agencia_id = ? AND estado = 'disponible' ORDER BY id DESC""", (agencia_id,))]
    return render_template(
        "web_agencia/config.html", ag=ag, cfg=cfg, sugerido=sugerido, vehiculos=vehiculos,
        landing_url=LANDING_URL, color=color_valido(ag["web_color"]), max_destacados=MAX_DESTACADOS,
        consultas_nuevas=query("SELECT COUNT(*) AS c FROM web_consultas WHERE agencia_id = ? AND estado = 'nuevo'", (agencia_id,), one=True)["c"],
        tiene_telefono=bool((cfg.get("telefono") or "").strip()),
    )


# ---------------------------------------------------------------- "Compramos tu auto"

def _limpiar(txt, largo):
    return re.sub(r"\s+", " ", str(txt or "")).strip()[:largo]


@bp.route("/a/<slug>/compramos", methods=["POST"])
def compramos(slug):
    """Formulario público "Compramos tu auto": guarda la consulta para la
    agencia y le avisa por mail. Anti-spam: campo trampa, límite por IP y por
    día. Nunca muestra datos de otras personas."""
    ag = query("SELECT id, nombre_agencia, email, activo, web_activa FROM agencias WHERE web_slug = ?",
               (slug.lower(),), one=True)
    if not ag or ag["activo"] == 0 or not ag["web_activa"]:
        return jsonify({"ok": False, "error": "Esta web no está disponible."}), 404
    f = request.form
    if f.get("sitio"):  # campo trampa: lo completan solo los robots
        return jsonify({"ok": True})
    nombre, tel = _limpiar(f.get("nombre"), 80), re.sub(r"[^\d+ ()\-]", "", _limpiar(f.get("telefono"), 30))
    marca, modelo = _limpiar(f.get("marca"), 40), _limpiar(f.get("modelo"), 60)
    comentario = _limpiar(f.get("comentario"), 500)
    try:
        anio = int(f.get("anio") or 0)
    except ValueError:
        anio = 0
    try:
        km = int(re.sub(r"\D", "", f.get("km") or "") or 0)
    except ValueError:
        km = 0
    if len(nombre) < 2 or len(re.sub(r"\D", "", tel)) < 8 or not marca or not modelo or not (1980 <= anio <= 2030):
        return jsonify({"ok": False, "error": "Completá nombre, teléfono, marca, modelo y año."}), 400
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip())[:45]
    por_ip = query("SELECT COUNT(*) AS c FROM web_consultas WHERE ip = ? AND created_at > datetime('now', '-1 hour')", (ip,), one=True)["c"]
    por_dia = query("SELECT COUNT(*) AS c FROM web_consultas WHERE agencia_id = ? AND created_at > datetime('now', '-1 day')", (ag["id"],), one=True)["c"]
    if por_ip >= 3 or por_dia >= 40:
        return jsonify({"ok": False, "error": "Recibimos varias consultas seguidas. Probá de nuevo en un rato o escribinos por WhatsApp."}), 429
    execute("""INSERT INTO web_consultas (agencia_id, tipo, nombre, telefono, marca, modelo, anio, km, comentario, ip)
               VALUES (?, 'compramos', ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ag["id"], nombre, tel, marca, modelo, anio, km or None, comentario or None, ip))
    try:
        from utils.notificaciones import avisar_agencia
        avisar_agencia(ag["email"], f"Nueva consulta en tu web: quieren vender un {marca} {modelo} {anio}",
                       f"{nombre} ({tel}) quiere vender su {marca} {modelo} {anio}"
                       + (f", {km:,} km".replace(",", ".") if km else "") + "."
                       + (f"\nComentario: {comentario}" if comentario else ""),
                       ruta="/mi-web/consultas")
    except Exception as e:
        print(f"[web_agencia] No se pudo avisar por mail: {e}")
    return jsonify({"ok": True})


@bp.route("/mi-web/consultas")
def consultas():
    from routes.stock import _whatsapp_ar
    agencia_id = session.get("agencia_id")
    if not agencia_id:
        return redirect(url_for("precios.index"))
    filas = []
    for c in query("SELECT * FROM web_consultas WHERE agencia_id = ? ORDER BY (estado = 'nuevo') DESC, id DESC LIMIT 200", (agencia_id,)):
        num = _whatsapp_ar(re.sub(r"[^\d]", "", c["telefono"] or ""))
        msg = f"Hola {c['nombre']}! Te escribo por tu {c['marca']} {c['modelo']} {c['anio']} que quisiste vender."
        filas.append(dict(c, wa=(f"https://wa.me/{num}?text={quote_plus(msg)}" if num else None)))
    return render_template("web_agencia/consultas.html", consultas=filas)


@bp.route("/mi-web/consultas/<int:cid>/atendida", methods=["POST"])
def consulta_atendida(cid):
    agencia_id = session.get("agencia_id")
    if not agencia_id:
        abort(403)
    execute("UPDATE web_consultas SET estado = CASE estado WHEN 'nuevo' THEN 'atendido' ELSE 'nuevo' END WHERE id = ? AND agencia_id = ?", (cid, agencia_id))
    return redirect(url_for("web_agencia.consultas"))
