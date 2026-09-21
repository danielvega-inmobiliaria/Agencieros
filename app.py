import json
import os
from flask import Flask, redirect, url_for, session, flash, send_from_directory, request, render_template, Response

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
    def _inject_puede_ver_todo():
        return {"puede_ver_todo": session.get("agencia_id") == 1}

    @app.context_processor
    def _inject_matches_pendientes():
        # Contador de matches pendientes de revisar, disponible en todos los
        # templates para el badge del menú (ver templates/base.html) — así
        # se ve desde cualquier pantalla que hay algo nuevo, sin depender de
        # entrar pedido por pedido (pedido de Daniel 15/09/2026, continuación
        # 27: "se me pasó por alto").
        # Multi-tenant (18/09/2026): Matches todavía no filtra por
        # agencia_id (está en MODULOS_SOLO_AGENCIA_1), así que este
        # contador solo se calcula para la agencia 1 -- para cualquier
        # otra agencia queda en 0 en vez de mostrar un número calculado
        # sobre pedidos que capaz no son suyos.
        if session.get("agencia_id") != 1:
            return {"matches_pendientes": 0}
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
            "auth.login", "auth.registro", "auth.verificar", "auth.reenviar_codigo",
            "static", "stock.ficha",
            # Landing pública (21/09/2026): "index" decide solo según el host
            # (landing en agencieros.net.ar, login en la app) e "inicio" es
            # la misma landing para poder verla desde la app.
            "index", "inicio", "robots_txt",
        }
        if request.endpoint and request.endpoint not in publicas and "agencia_id" not in session:
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

    # Red de Agencieros multi-tenant (18/09/2026): por ahora solo la
    # agencia 1 (Italia Automotores, la de Daniel) tiene estos módulos
    # separados y probados por agencia -- el resto ya tiene la columna
    # `agencia_id` en la base (ver database.py) pero las rutas todavía no
    # filtran por ella. Hasta que se escale módulo por módulo, cualquier
    # otra agencia que se registre queda bloqueada acá (nunca llega a ver
    # datos de Italia Automotores ni de otra agencia por un WHERE que
    # todavía falta agregar) -- ver Pendientes en PROYECTO.md para el
    # orden en que se van habilitando.
    # Stock salió de esta lista el 18/09/2026: ya filtra todo por
    # `agencia_id` (routes/stock.py, buscador.py, sync_stock.py) y quedó
    # probado con una 2da agencia de prueba antes de habilitarlo acá.
    # Pedidos (Banco de pedidos) salió el 18/09/2026: ya filtra todo por
    # `agencia_id` (routes/pedidos.py), con "Red" a propósito sin filtrar
    # (mercado compartido), y quedó probado con una 2da agencia de prueba.
    # Toma y tasación (tomas, inspeccion, tasacion) salió el 20/09/2026: la Toma
    # y su Tasación guardan `agencia_id`, todas las rutas verifican que la Toma
    # sea de la agencia logueada y las tasaciones ofrecidas como permuta también
    # son solo las propias (routes/tomas.py, routes/stock.py, routes/financiacion.py).
    # Dashboard salió el 21/09/2026: todos sus números (stock por estado,
    # pedidos activos, ventas/ingresos/ganancia del mes, señas y permutas por
    # resolver, gastos en reparación, cuotas) filtran por la agencia logueada
    # (routes/dashboard.py). Las tarjetas que llevan a Financiación/Finanzas
    # (todavía bloqueadas) se ocultan o quedan sin link para las demás
    # agencias (templates/dashboard.html).
    MODULOS_SOLO_AGENCIA_1 = {
        "finanzas", "financiacion", "matches", "plataforma",
    }

    @app.before_request
    def _bloquear_modulos_sin_escalar():
        from flask import request
        endpoint = request.endpoint or ""
        blueprint = endpoint.split(".")[0]
        if blueprint in MODULOS_SOLO_AGENCIA_1 and session.get("agencia_id") != 1:
            flash(
                "Este módulo todavía no está habilitado para agencias nuevas -- "
                "por ahora podés usar Dashboard, Stock, Banco de pedidos, Toma y tasación, "
                "Red de Agencieros, Consulta de precios y tu Admin.",
                "error",
            )
            return redirect(url_for("red.index"))

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
