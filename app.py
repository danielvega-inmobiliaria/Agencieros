import json
import mimetypes
import os
from flask import Flask, redirect, url_for, session, flash, send_from_directory, request, render_template, Response

mimetypes.add_type("application/manifest+json", ".webmanifest")

from database import init_db, close_db, obtener_catalogo
from storage import uploads_dir

# Landing pública (21/09/2026): agencieros.net.ar y www.agencieros.net.ar
# apuntan a esta misma app (mismo Railway, mismo patrón que PresupuestoPRO) y
# muestran la presentación del producto; la app en sí vive en
# app.agencieros.net.ar (variable APP_URL). Cualquier otra ruta pedida en el
# dominio raíz (/auth/login, /stock, etc.) se redirige a la app.
LANDING_HOSTS = {"agencieros.net.ar", "www.agencieros.net.ar"}
APP_URL = os.environ.get("APP_URL", "https://app.agencieros.net.ar").rstrip("/")
LANDING_URL = os.environ.get("LANDING_URL", "https://agencieros.net.ar").rstrip("/")

# Meta Pixel (21/09/2026) -- ver 05_MARKETING/META_ADS/CAMPANA_AGENCIEROS.md.
# Sin META_PIXEL_ID cargada en el entorno, el Pixel simplemente no se
# imprime en ningun template (ver templates/partials/meta_pixel.html):
# se puede pushear este codigo ya mismo y activar el Pixel despues nomas
# cargando la variable en Railway, sin otro deploy.
META_PIXEL_ID = os.environ.get("META_PIXEL_ID", "").strip()
# "Sincronizar desde STOCK" lee la carpeta 03_AUTOMOTOR/STOCK de la compu de
# Daniel: es un dato de Italia Automotores (agencia 1), no un permiso de admin.
STOCK_SYNC_AGENCIA_ID = int(os.environ.get("STOCK_SYNC_AGENCIA_ID", "1"))
META_DOMAIN_VERIFICATION = os.environ.get("META_DOMAIN_VERIFICATION", "").strip()


def _es_host_landing():
    host = (request.host or "").split(":")[0].lower()
    return host in LANDING_HOSTS


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-agencieros-cambiar-en-produccion")

    with app.app_context():
        init_db()

    app.teardown_appcontext(close_db)

    from routes.auth import bp as auth_bp
    from routes.dashboard import bp as dashboard_bp
    from routes.precios import bp as precios_bp
    from routes.stock import bp as stock_bp
    from routes.pedidos import bp as pedidos_bp
    from routes.tomas import bp as tomas_bp
    from routes.inspeccion import bp as inspeccion_bp
    from routes.tasacion import bp as tasacion_bp
    from routes.finanzas import bp as finanzas_bp
    from routes.red import bp as red_bp
    from routes.financiacion import bp as financiacion_bp
    from routes.matches import bp as matches_bp
    from routes.admin import bp as admin_bp
    from routes.plataforma import bp as plataforma_bp
    from routes.ml import bp as ml_bp
    from routes.mensajes import bp as mensajes_bp
    from routes.cuenta import bp as cuenta_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(precios_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(pedidos_bp)
    app.register_blueprint(tomas_bp)
    app.register_blueprint(inspeccion_bp)
    app.register_blueprint(tasacion_bp)
    app.register_blueprint(finanzas_bp)
    app.register_blueprint(red_bp)
    app.register_blueprint(financiacion_bp)
    app.register_blueprint(matches_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(plataforma_bp)
    app.register_blueprint(ml_bp)
    app.register_blueprint(mensajes_bp)
    app.register_blueprint(cuenta_bp)

    @app.template_filter("fecha_ar")
    def _fecha_ar(valor):
        # "YYYY-MM-DD HH:MM:SS" en UTC (datetime('now') de SQLite) -> hora
        # de Argentina, "DD/MM/YYYY HH:MM".
        from datetime import datetime, timedelta
        try:
            d = datetime.strptime(str(valor)[:19], "%Y-%m-%d %H:%M:%S") - timedelta(hours=3)
            return d.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return valor or ""

    @app.before_request
    def _landing_host():
        # En el dominio raíz solo se sirven la landing, robots.txt y los
        # estáticos; el resto se manda a la app (mismo path y query).
        if not _es_host_landing():
            return None
        if request.endpoint in {"index", "inicio", "robots_txt", "static"}:
            return None
        destino = APP_URL + request.full_path
        if destino.endswith("?"):
            destino = destino[:-1]
        return redirect(destino, code=302)

    @app.context_processor
    def _inject_catalogo():
        # Catálogo unificado de Marca/Modelo/Versión (ver database.obtener_catalogo)
        # disponible en todos los templates para armar los selects en cascada.
        try:
            return {"catalogo_json": json.dumps(obtener_catalogo(), ensure_ascii=False)}
        except Exception:
            return {"catalogo_json": "{}"}

    @app.context_processor
    def _inject_navegacion():
        # "‹ Volver" y "Anterior / Siguiente" comunes (30/09/2026) -- ver utils/navegacion.py.
        from utils.navegacion import volver_auto, nav_detalle
        try:
            return {"volver_auto": volver_auto(), "nav_detalle": nav_detalle()}
        except Exception:
            return {"volver_auto": None, "nav_detalle": None}

    @app.context_processor
    def _inject_rol():
        from utils.permisos import es_vendedor, es_dueno
        return {"es_vendedor": es_vendedor(), "es_dueno": es_dueno()}

    @app.context_processor
    def _inject_demo():
        return {"es_demo": bool(session.get("es_demo"))}

    # Demo (06/10/2026): se puede cargar y probar todo, pero no tocar cuentas
    # ni mandar mensajes (le llegarían al administrador).
    DEMO_BLOQUEADOS = {"cuenta.index", "cuenta.usuario_nuevo", "cuenta.usuario_editar", "mensajes.index"}

    @app.before_request
    def _proteger_demo():
        if session.get("es_demo") and request.method == "POST" and (request.endpoint or "") in DEMO_BLOQUEADOS:
            flash("En la demo esta acción está desactivada. ¡Registrá tu agencia para usarla!", "error")
            return redirect(request.referrer or url_for("dashboard.index"))
        return None

    @app.context_processor
    def _inject_superadmin():
        # 28/09/2026: el admin de la plataforma es un usuario aparte
        # (tabla plataforma_admins), ya no la agencia 1.
        return {
            "es_superadmin": bool(session.get("superadmin_id")),
            "puede_sincronizar_stock": session.get("agencia_id") == STOCK_SYNC_AGENCIA_ID,
            "zona_deautos": session.get("agencia_id") == STOCK_SYNC_AGENCIA_ID,
        }

    @app.context_processor
    def _inject_mensajes_nuevos():
        # Badge de mensajes sin leer: para el admin, los de las agencias; para
        # una agencia, las respuestas del admin que todavía no vio.
        from database import query
        if session.get("agencia_id"):
            try:
                fila = query("SELECT COUNT(*) AS c FROM mensajes_admin WHERE agencia_id = ? AND leido_agencia = 0",
                             (session["agencia_id"],), one=True)
                return {"respuestas_nuevas": fila["c"]}
            except Exception:
                return {"respuestas_nuevas": 0}
        if not session.get("superadmin_id"):
            return {}
        try:
            fila = query("SELECT COUNT(*) AS c FROM mensajes_admin WHERE leido = 0", one=True)
            return {"mensajes_nuevos": fila["c"]}
        except Exception:
            return {"mensajes_nuevos": 0}

    @app.context_processor
    def _inject_meta_pixel():
        return {"meta_pixel_id": META_PIXEL_ID, "meta_domain_verification": META_DOMAIN_VERIFICATION}

    @app.context_processor
    def _inject_fb_eventos():
        # Eventos de conversion del Pixel pendientes de disparar (ver
        # routes/auth.py::verificar y routes/stock.py::nuevo), mostrados
        # una sola vez en la primera pagina que renderiza despues de la
        # accion real (nunca por un parametro de URL, que se pierde o se
        # puede repetir con solo recargar) -- misma logica que resolvio el
        # problema de PresupuestoPRO con CompleteRegistration.
        return {"fb_eventos_pendientes": session.pop("fb_eventos_pendientes", [])}

    @app.context_processor
    def _inject_matches_pendientes():
        # Contador de matches pendientes de revisar, disponible en todos los
        # templates para el badge del menú (ver templates/base.html) — así
        # se ve desde cualquier pantalla que hay algo nuevo, sin depender de
        # entrar pedido por pedido (pedido de Daniel 15/09/2026, continuación
        # 27: "se me pasó por alto").
        # Multi-tenant (21/09/2026): Matches ya filtra por agencia_id
        # (contar_matches usa session["agencia_id"] internamente), así que
        # el badge se calcula igual para cualquier agencia.
        from routes.matches import contar_matches
        try:
            return {"matches_pendientes": contar_matches()}
        except Exception:
            return {"matches_pendientes": 0}

    @app.before_request
    def _require_login():
        from flask import request
        # "stock.ficha" queda pública a propósito: es la ficha comercial
        # para compartir por WhatsApp/historias con un comprador que no
        # tiene (ni necesita) usuario en la app (pedido de Daniel
        # 16/09/2026).
        publicas = {
            "auth.login", "auth.registro", "auth.verificar", "auth.reenviar_codigo", "auth.demo",
            "static", "stock.ficha",
            # Fotos y logos subidos: la ficha compartida es pública y sin
            # esto quien la abre sin sesión (el cliente) no veía las fotos.
            "uploads_estaticas",
            # Landing pública (21/09/2026): "index" decide solo según el host
            # (landing en agencieros.net.ar, login en la app) e "inicio" es
            # la misma landing para poder verla desde la app.
            "index", "inicio", "robots_txt",
        }
        if (request.endpoint and request.endpoint not in publicas
                and "agencia_id" not in session and "superadmin_id" not in session):
            return redirect(url_for("auth.login"))

    @app.before_request
    def _registrar_actividad():
        # "Última actividad" por agencia (18/09/2026, Panel de Agencias) --
        # se pisa en cada request autenticado (salvo estáticos) para que el
        # panel de plataforma.agencias pueda mostrar qué tan viva está cada
        # agencia de la Red. Sin throttle: son pocas agencias y un UPDATE
        # por request no pesa nada en SQLite -- si el volumen crece se puede
        # limitar a 1 vez cada X minutos por sesión más adelante.
        from flask import request
        agencia_id = session.get("agencia_id")
        if agencia_id and request.endpoint != "static":
            from database import execute
            try:
                execute(
                    "UPDATE agencias SET ultima_actividad = datetime('now') WHERE id = ?",
                    (agencia_id,),
                )
            except Exception:
                pass

    # Separación Admin de la plataforma / agencias (28/09/2026). Antes la
    # agencia 1 (Italia Automotores) era a la vez agencia y dueña de la
    # plataforma (MODULOS_SOLO_AGENCIA_1). Ahora:
    # - El admin de la plataforma (session["superadmin_id"], tabla
    #   plataforma_admins) no tiene agencia: solo ve Panel de Agencias,
    #   MercadoLibre, Consulta de precios y la Red (para moderar).
    # - Las agencias (Italia incluida) no pueden entrar a esos módulos de
    #   administración.
    SOLO_SUPERADMIN = {"plataforma", "ml"}
    SUPERADMIN_PERMITIDOS = {"plataforma", "ml", "precios", "auth", "static"}
    SUPERADMIN_ENDPOINTS = {"red.index", "red.cerrar", "index", "inicio", "robots_txt", "cuenta.index"}

    @app.before_request
    def _usuario_de_agencia():
        # Usuarios por agencia (28/09/2026). Sesiones abiertas antes de este
        # cambio solo tienen agencia_id: se completan con el dueño de la
        # agencia, así nadie tiene que volver a ingresar. En cada request se
        # verifica que el usuario siga activo (si el dueño lo desactiva,
        # queda afuera en el próximo click) y se toma el rol vigente.
        agencia_id = session.get("agencia_id")
        if not agencia_id or request.endpoint in (None, "static", "auth.logout"):
            return None
        from database import query
        try:
            if session.get("usuario_id"):
                u = query("SELECT id, nombre, email, rol, activo FROM agencia_usuarios WHERE id = ? AND agencia_id = ?",
                          (session["usuario_id"], agencia_id), one=True)
            else:
                u = query("""SELECT id, nombre, email, rol, activo FROM agencia_usuarios
                             WHERE agencia_id = ? AND activo = 1
                             ORDER BY CASE WHEN lower(email) = lower(?) THEN 0 ELSE 1 END,
                                      CASE rol WHEN 'dueno' THEN 0 ELSE 1 END, id LIMIT 1""",
                          (agencia_id, session.get("agencia_email") or ""), one=True)
        except Exception:
            return None
        if not u or not u["activo"]:
            session.clear()
            flash("Tu usuario fue desactivado. Consultá con el dueño de la agencia.", "error")
            return redirect(url_for("auth.login"))
        session["usuario_id"] = u["id"]
        session["usuario_nombre"] = u["nombre"]
        session["usuario_email"] = u["email"]
        session["usuario_rol"] = u["rol"]
        return None

    @app.before_request
    def _permisos_vendedor():
        from utils.permisos import es_vendedor, BLUEPRINTS_SOLO_DUENO, ENDPOINTS_SOLO_DUENO
        if not session.get("agencia_id") or not es_vendedor():
            return None
        endpoint = request.endpoint or ""
        if endpoint.split(".")[0] in BLUEPRINTS_SOLO_DUENO or endpoint in ENDPOINTS_SOLO_DUENO:
            flash("Esa sección es solo para el dueño de la agencia.", "error")
            return redirect(url_for("precios.index"))
        return None

    @app.before_request
    def _separar_superadmin():
        from flask import request
        endpoint = request.endpoint or ""
        blueprint = endpoint.split(".")[0]
        if session.get("superadmin_id"):
            if blueprint in SUPERADMIN_PERMITIDOS or endpoint in SUPERADMIN_ENDPOINTS:
                return None
            if endpoint == "stock.ficha":
                return None
            flash("Con la cuenta de administración de la plataforma no se cargan datos de agencia.", "error")
            return redirect(url_for("plataforma.agencias"))
        if blueprint in SOLO_SUPERADMIN:
            flash("Esa sección es solo para la administración de AGENCIEROS.", "error")
            return redirect(url_for("precios.index"))
        return None

    def _render_landing():
        # En el dominio raíz los botones apuntan a la app (URL absoluta); si
        # se ve la landing desde la propia app (/inicio) alcanzan los links
        # relativos.
        en_landing = _es_host_landing()
        return render_template(
            "landing.html",
            app_url=APP_URL if en_landing else "",
            landing_url=LANDING_URL,
        )

    @app.route("/")
    def index():
        if _es_host_landing():
            return _render_landing()
        # En la app, la Consulta de precios es la pantalla principal.
        return redirect(url_for("precios.index"))

    @app.route("/inicio")
    def inicio():
        return _render_landing()

    @app.route("/robots.txt")
    def robots_txt():
        if _es_host_landing():
            cuerpo = "User-agent: *\nAllow: /\n"
        else:
            # La app (y las fichas compartidas por WhatsApp) no se indexan.
            cuerpo = "User-agent: *\nDisallow: /\n"
        return Response(cuerpo, mimetype="text/plain")

    # Intercepta /static/uploads/... para servir las fotos desde el volumen
    # persistente de Railway (storage.uploads_dir()) en vez de la carpeta
    # static/ del codigo, que en Railway se pisa en cada redeploy. Las URLs
    # guardadas en la base no cambian (siguen siendo /static/uploads/...),
    # asi que las fotos ya subidas no se rompen -- en local, uploads_dir()
    # apunta a la misma carpeta static/uploads de siempre.
    @app.route("/static/uploads/<path:filename>")
    def uploads_estaticas(filename):
        return send_from_directory(uploads_dir(), filename)

    return app


app = create_app()

if __name__ == "__main__":
    # host="0.0.0.0": escucha en toda la red local, no solo en esta PC,
    # así se puede entrar desde el celu (u otra compu) conectado al mismo WiFi.
    app.run(host="0.0.0.0", debug=True, port=5000)
