import json
import os
from flask import Flask, redirect, url_for, session, flash, send_from_directory

from database import init_db, close_db, obtener_catalogo
from storage import uploads_dir


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
        }
        if request.endpoint and request.endpoint not in publicas and "agencia_id" not in session:
            return redirect(url_for("auth.login"))

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
    MODULOS_SOLO_AGENCIA_1 = {
        "dashboard", "tomas", "inspeccion",
        "tasacion", "finanzas", "financiacion", "matches",
    }

    @app.before_request
    def _bloquear_modulos_sin_escalar():
        from flask import request
        endpoint = request.endpoint or ""
        blueprint = endpoint.split(".")[0]
        if blueprint in MODULOS_SOLO_AGENCIA_1 and session.get("agencia_id") != 1:
            flash(
                "Este módulo todavía no está habilitado para agencias nuevas -- "
                "por ahora podés usar Red de Agencieros, Consulta de precios y tu Admin.",
                "error",
            )
            return redirect(url_for("red.index"))

    @app.route("/")
    def index():
        # La Consulta de precios es la pantalla principal del producto.
        return redirect(url_for("precios.index"))

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
