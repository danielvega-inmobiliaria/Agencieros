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
from datetime import datetime, timedelta
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
DIAS_NUEVO = 15   # "Recién ingresados": autos cargados en los últimos N días
DIAS_BAJA = 30    # "Bajaron de precio": baja de precio en los últimos N días
VENDE_OPCIONES = ("usados", "0km", "ambos")


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
                  COALESCE(web_ocultar_precio, 0) AS ocultar_precio, COALESCE(web_destacado, 0) AS destacado,
                  CASE WHEN COALESCE(fecha_ingreso, '') >= date('now', '-%d day') THEN 1 ELSE 0 END AS es_nuevo,
                  CASE WHEN COALESCE(precio_baja_fecha, '') >= date('now', '-%d day')
                            AND COALESCE(precio_anterior, 0) > COALESCE(valor_publicado, 0) AND COALESCE(valor_publicado, 0) > 0
                       THEN 1 ELSE 0 END AS es_baja,
                  precio_anterior
           FROM vehiculos
           WHERE agencia_id = ? AND estado = 'disponible' AND COALESCE(web_visible, 1) = 1
           ORDER BY id DESC""" % (DIAS_NUEVO, DIAS_BAJA), (agencia_id,))
    items = []
    for v in filas:
        titulo = " ".join(str(x) for x in [v["marca"], v["modelo"]] if x)
        items.append({
            "id": v["id"], "titulo": titulo, "modelo": v["modelo"] or "", "version": v["version"] or "", "marca": v["marca"] or "",
            "anio": v["anio"], "km": v["km"],
            # km == 0 cargado a propósito = 0 Km (km vacío = no se sabe, es usado).
            "cero_km": v["km"] is not None and int(v["km"]) == 0,
            "km_txt": "0 km" if (v["km"] is not None and int(v["km"]) == 0)
                      else (f"{int(v['km']):,} km".replace(",", ".") if v["km"] else ""),
            "combustible": v["combustible"] or "", "caja": v["caja"] or "",
            "precio": 0 if v["ocultar_precio"] else (v["valor_publicado"] or 0),
            "precio_txt": _pesos(v["valor_publicado"]) if (v["valor_publicado"] and not v["ocultar_precio"]) else "Consultar",
            "foto": foto_principal(v["id"]), "destacado": bool(v["destacado"]),
            "nuevo": bool(v["es_nuevo"]),
            # "Bajó de precio" solo si el precio se muestra (si está oculto no se delata la baja).
            "baja": bool(v["es_baja"]) and not v["ocultar_precio"],
            "precio_ant_txt": _pesos(v["precio_anterior"]) if (v["es_baja"] and not v["ocultar_precio"]) else "",
            "ficha": f"{APP_URL}/stock/{v['id']}/ficha?wa=0&web={slug}",
        })
    return items


@bp.route("/a/<slug>")
def pagina(slug):
    from routes.stock import _whatsapp_ar, _redes_ordenadas
    ag = query("SELECT id, nombre_agencia, activo, web_activa, web_color, web_vende FROM agencias WHERE web_slug = ?",
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
    # Qué vende la agencia manda sobre cómo se arma la web. Sin definir
    # (agencias anteriores): se deduce de los autos cargados, como antes.
    vende = ag["web_vende"] if ag["web_vende"] in VENDE_OPCIONES else None
    if vende == "usados":
        hay_cero, hay_usados = False, True
    elif vende == "0km":
        hay_cero, hay_usados = True, False
    elif vende == "ambos":
        hay_cero, hay_usados = True, True
    else:
        hay_cero, hay_usados = any(i["cero_km"] for i in items), any(not i["cero_km"] for i in items)
    tipo_titulo = ("Autos 0 Km y usados" if (hay_cero and hay_usados) else ("Autos 0 Km" if hay_cero else "Autos usados"))
    og_img = items[0]["foto"] if items else cfg.get("logo_url")
    if og_img and og_img.startswith("/"):
        og_img = APP_URL + og_img
    return render_template(
        "web_agencia/pagina.html", nombre=nombre, cfg=cfg, lugar=lugar, items=items,
        marcas=sorted({i["marca"] for i in items if i["marca"]}),
        wa_general=(f"{wa_base}?text={quote_plus('Hola! Vi tu web y quiero consultar por un auto.')}" if wa_base else None),
        url_canonica=f"{LANDING_URL}/a/{slug.lower()}", og_img=og_img,
        destacados=[i for i in items if i["destacado"]][:MAX_DESTACADOS], slug=slug.lower(),
        hay_cero=hay_cero, hay_usados=hay_usados, tipo_titulo=tipo_titulo, solo_cero=(hay_cero and not hay_usados),
        n_nuevos=sum(1 for i in items if i["nuevo"]), n_bajas=sum(1 for i in items if i["baja"]),
        dias_nuevo=DIAS_NUEVO, dias_baja=DIAS_BAJA,
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
    ag = query("SELECT id, nombre_agencia, web_slug, web_activa, web_color, web_vende FROM agencias WHERE id = ?", (agencia_id,), one=True)
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
        vende = request.form.get("vende")
        vende = vende if vende in VENDE_OPCIONES else (ag["web_vende"] if ag["web_vende"] in VENDE_OPCIONES else None)
        if activa and not vende:
            flash("Antes de publicar tu web contanos qué vendés: solo usados, solo 0 Km o ambos. Así la armamos como corresponde.", "error")
            return redirect(url_for("web_agencia.config"))
        color = color_valido(request.form.get("color"))
        execute("UPDATE agencias SET web_slug = ?, web_activa = ?, web_color = ?, web_vende = ? WHERE id = ?",
                (slug, activa, color, vende, agencia_id))
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
        """SELECT id, marca, modelo, version, anio, km, valor_publicado, COALESCE(web_visible, 1) AS web_visible,
                  COALESCE(web_ocultar_precio, 0) AS ocultar_precio, COALESCE(web_destacado, 0) AS destacado
           FROM vehiculos WHERE agencia_id = ? AND estado = 'disponible' ORDER BY id DESC""", (agencia_id,))]
    return render_template(
        "web_agencia/config.html", ag=ag, cfg=cfg, sugerido=sugerido, vehiculos=vehiculos,
        landing_url=LANDING_URL, color=color_valido(ag["web_color"]), max_destacados=MAX_DESTACADOS,
        consultas_nuevas=query("SELECT COUNT(*) AS c FROM web_consultas WHERE agencia_id = ? AND estado = 'nuevo' AND tipo = 'compramos'", (agencia_id,), one=True)["c"],
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
    execute("""INSERT INTO web_consultas (agencia_id, tipo, origen, nombre, telefono, marca, modelo, anio, km, comentario, ip)
               VALUES (?, 'compramos', 'form', ?, ?, ?, ?, ?, ?, ?, ?)""",
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


ESTADOS = ("nuevo", "contactado", "seguimiento", "cerrado")
ESTADO_TXT = {"nuevo": "Nueva", "contactado": "Contactada", "seguimiento": "En seguimiento", "cerrado": "Cerrada"}


def _hoy_ar():
    return (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d")


def _registrar_clic(ag_id, vehiculo, origen):
    """Clic en un botón de WhatsApp de la web o la ficha: queda en la bandeja
    como interés sin datos de contacto. Anónimo, sin mail. Los clics de la
    propia agencia no cuentan; un mismo visitante cuenta una vez por auto cada 6 h."""
    if session.get("agencia_id") == ag_id or session.get("superadmin_id"):
        return
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip())[:45]
    vid = vehiculo["id"] if vehiculo else None
    if query("SELECT COUNT(*) AS c FROM web_consultas WHERE ip = ? AND tipo = 'wa_clic' AND created_at > datetime('now', '-1 hour')",
             (ip,), one=True)["c"] >= 30:
        return
    if query("""SELECT 1 FROM web_consultas WHERE ip = ? AND tipo = 'wa_clic' AND agencia_id = ? AND COALESCE(vehiculo_id, 0) = ?
                AND created_at > datetime('now', '-6 hours')""", (ip, ag_id, vid or 0), one=True):
        return
    txt = None
    if vehiculo:
        txt = " ".join(str(x) for x in [vehiculo["marca"], vehiculo["modelo"], vehiculo["version"]] if x)
        if vehiculo["anio"]:
            txt += f" ({vehiculo['anio']})"
    execute("""INSERT INTO web_consultas (agencia_id, tipo, origen, marca, modelo, anio, vehiculo_id, vehiculo_txt, ip)
               VALUES (?, 'wa_clic', ?, ?, ?, ?, ?, ?, ?)""",
            (ag_id, origen, vehiculo["marca"] if vehiculo else None, vehiculo["modelo"] if vehiculo else None,
             vehiculo["anio"] if vehiculo else None, vid, txt, ip))


@bp.route("/clic/<int:vid>", methods=["POST"])
def clic_auto(vid):
    v = query("SELECT id, agencia_id, marca, modelo, version, anio FROM vehiculos WHERE id = ? AND estado = 'disponible'", (vid,), one=True)
    if v:
        try:
            _registrar_clic(v["agencia_id"] or 1, v, "wa_ficha" if request.args.get("o") == "ficha" else "wa_web")
        except Exception as e:
            print(f"[web_agencia] No se pudo registrar el clic: {e}")
    return ("", 204)


@bp.route("/a/<slug>/clic", methods=["POST"])
def clic_web(slug):
    ag = query("SELECT id FROM agencias WHERE web_slug = ? AND activo != 0 AND web_activa = 1", (slug.lower(),), one=True)
    if ag:
        try:
            _registrar_clic(ag["id"], None, "wa_web")
        except Exception as e:
            print(f"[web_agencia] No se pudo registrar el clic: {e}")
    return ("", 204)


@bp.route("/mi-web/consultas")
def consultas():
    """Bandeja simple: quienes quieren vender su auto («Compramos tu auto»).
    Dos estados: pendiente y atendida. Los clics de WhatsApp no son tarjetas:
    se ven como contador en cada auto de Stock."""
    from routes.stock import _whatsapp_ar
    agencia_id = session.get("agencia_id")
    if not agencia_id:
        return redirect(url_for("precios.index"))
    ver = "atendidas" if request.args.get("ver") == "atendidas" else "pendientes"
    cuentas = {"pendientes": 0, "atendidas": 0}
    for r in query("SELECT estado, COUNT(*) AS c FROM web_consultas WHERE agencia_id = ? AND tipo = 'compramos' GROUP BY estado", (agencia_id,)):
        cuentas["pendientes" if r["estado"] == "nuevo" else "atendidas"] += r["c"]
    filas = []
    for c in query("SELECT * FROM web_consultas WHERE agencia_id = ? AND tipo = 'compramos' AND estado " + ("!=" if ver == "atendidas" else "=") + " 'nuevo' ORDER BY id DESC LIMIT 200", (agencia_id,)):
        num = _whatsapp_ar(re.sub(r"[^\d]", "", c["telefono"] or ""))
        msg = f"Hola {c['nombre']}! Te escribo por tu {c['marca']} {c['modelo']} {c['anio']} que quisiste vender."
        filas.append(dict(c, wa=(f"https://wa.me/{num}?text={quote_plus(msg)}" if num else None)))
    return render_template("web_agencia/consultas.html", consultas=filas, ver=ver, cuentas=cuentas)


@bp.route("/mi-web/consultas/<int:cid>/actualizar", methods=["POST"])
def consulta_actualizar(cid):
    agencia_id = session.get("agencia_id")
    if not agencia_id:
        abort(403)
    c = query("SELECT * FROM web_consultas WHERE id = ? AND agencia_id = ?", (cid, agencia_id), one=True)
    if not c:
        abort(404)
    f = request.form
    estado = f.get("estado") if f.get("estado") in ESTADOS else c["estado"]
    nota = _limpiar(f.get("nota"), 500) if "nota" in f else (c["nota"] or "")
    seg = c["seguimiento"] or ""
    if "seguimiento" in f:
        seg = f.get("seguimiento", "").strip()
        seg = seg if re.fullmatch(r"\d{4}-\d{2}-\d{2}", seg) else ""
    if estado == "seguimiento" and not seg:
        seg = (datetime.utcnow() - timedelta(hours=3) + timedelta(days=1)).strftime("%Y-%m-%d")
    if estado == "cerrado":
        seg = ""
    execute("UPDATE web_consultas SET estado = ?, nota = ?, seguimiento = ?, updated_at = datetime('now') WHERE id = ? AND agencia_id = ?",
            (estado, nota or None, seg or None, cid, agencia_id))
    return redirect(url_for("web_agencia.consultas", ver=f.get("ver") or "nuevas", tipo=f.get("tipo") or "todas") + f"#c{cid}")


@bp.route("/mi-web/consultas/<int:cid>/atendida", methods=["POST"])
def consulta_atendida(cid):
    """Compatibilidad con el botón anterior: nuevo <-> contactado."""
    agencia_id = session.get("agencia_id")
    if not agencia_id:
        abort(403)
    execute("UPDATE web_consultas SET estado = CASE estado WHEN 'nuevo' THEN 'contactado' ELSE 'nuevo' END, updated_at = datetime('now') WHERE id = ? AND agencia_id = ?", (cid, agencia_id))
    return redirect(url_for("web_agencia.consultas"))
