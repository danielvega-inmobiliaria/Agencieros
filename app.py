import json
import os
from flask import Flask, redirect, url_for, session

from database import init_db, close_db, obtener_catalogo


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

    @app.context_processor
    def _inject_catalogo():
        # Catálogo unificado de Marca/Modelo/Versión (ver database.obtener_catalogo)
        # disponible en todos los templates para armar los selects en cascada.
        try:
            return {"catalogo_json": json.dumps(obtener_catalogo(), ensure_ascii=False)}
        except Exception:
            return {"catalogo_json": "{}"}

    @app.before_request
    def _require_login():
        from flask import request
        publicas = {"auth.login", "static"}
        if request.endpoint and request.endpoint not in publicas and "user_id" not in session:
            return redirect(url_for("auth.login"))

    @app.route("/")
    def index():
        # La Consulta de precios es la pantalla principal del producto.
        return redirect(url_for("precios.index"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
