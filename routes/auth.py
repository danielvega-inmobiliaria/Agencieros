"""Login/registro de agencias (Red de Agencieros multi-tenant, 18/09/2026).

Cada agencia que se registra tiene su propia cuenta (email + contraseña,
sin cobro todavía) y, al validar el mail con el código de 6 dígitos, su
propia copia separada de toda la app -- ver `agencia_id` en cada tabla de
negocio y el filtro por sesión en cada ruta. La agencia de Daniel
(Italia Automotores, id 1) ya quedó creada por la migración
`_migrar_multi_tenant_agencias` en `database.py`, con el mismo email y
contraseña que ya tenía.
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash

from database import query, execute
from routes.admin import PROVINCIAS_AR
from utils.verificacion import crear_codigo, validar_codigo, enviar_codigo_email

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _loguear(agencia):
    session["agencia_id"] = agencia["id"]
    session["agencia_nombre"] = agencia["nombre_agencia"]
    session["agencia_email"] = agencia["email"]


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        agencia = query("SELECT * FROM agencias WHERE email = ?", (email,), one=True)
        if not agencia or not check_password_hash(agencia["password_hash"], password):
            flash("Email o contraseña incorrectos.", "error")
            return render_template("auth/login.html")
        if not agencia["activo"]:
            flash("Esta cuenta está desactivada.", "error")
            return render_template("auth/login.html")
        if not agencia["email_verificado"]:
            # Sin validar todavía -- manda un código nuevo y lo lleva
            # directo a la pantalla de verificación en vez de dejarlo
            # entrar (mismo criterio que el registro).
            codigo = crear_codigo(agencia["id"])
            enviar_codigo_email(agencia["email"], agencia["nombre_agencia"], codigo)
            session["agencia_pendiente_id"] = agencia["id"]
            flash("Todavía no validaste tu mail -- te mandamos un código nuevo.", "error")
            return redirect(url_for("auth.verificar"))
        _loguear(agencia)
        return redirect(url_for("precios.index"))
    return render_template("auth/login.html")


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre_agencia = request.form.get("nombre_agencia", "").strip()
        email = request.form.get("email", "").strip().lower()
        # Teléfono: se aceptan espacios, guiones, paréntesis y "+" al tipear,
        # pero se guarda solo con números (mismo criterio que Admin).
        telefono = "".join(ch for ch in request.form.get("telefono", "") if ch not in " -()+.")
        direccion = request.form.get("direccion", "").strip()
        ciudad = request.form.get("ciudad", "").strip()
        provincia = request.form.get("provincia", "").strip()
        contacto_referencia = request.form.get("contacto_referencia", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        # Obligatorios (Daniel 21/09/2026): nombre de la agencia, teléfono,
        # dirección, ciudad, provincia y contacto de referencia -- así el Panel de Agencias y la Red
        # tienen siempre dónde ubicar y cómo contactar a cada agencia.
        if not nombre_agencia or not telefono or not direccion or not ciudad or not provincia or not contacto_referencia or not email or not password:
            flash(
                "Completá nombre de la agencia, teléfono, dirección, ciudad, provincia, contacto de referencia, email y contraseña.",
                "error",
            )
            return render_template("auth/registro.html", prev=request.form, provincias=PROVINCIAS_AR)
        if not telefono.isdigit() or not 8 <= len(telefono) <= 15:
            flash(
                "El teléfono tiene que tener solo números, con código de área (ej: 3413017371).",
                "error",
            )
            return render_template("auth/registro.html", prev=request.form, provincias=PROVINCIAS_AR)
        if provincia not in PROVINCIAS_AR:
            flash("Elegí una provincia de la lista.", "error")
            return render_template("auth/registro.html", prev=request.form, provincias=PROVINCIAS_AR)
        if len(password) < 6:
            flash("La contraseña tiene que tener al menos 6 caracteres.", "error")
            return render_template("auth/registro.html", prev=request.form, provincias=PROVINCIAS_AR)
        if password != password2:
            flash("Las contraseñas no coinciden.", "error")
            return render_template("auth/registro.html", prev=request.form, provincias=PROVINCIAS_AR)
        if query("SELECT id FROM agencias WHERE email = ?", (email,), one=True):
            flash("Ya hay una cuenta registrada con ese email.", "error")
            return render_template("auth/registro.html", prev=request.form, provincias=PROVINCIAS_AR)

        agencia_id = execute(
            """INSERT INTO agencias
               (nombre_agencia, email, password_hash, telefono, contacto_referencia, email_verificado, activo)
               VALUES (?, ?, ?, ?, ?, 0, 1)""",
            (nombre_agencia, email, generate_password_hash(password), telefono, contacto_referencia),
        )
        # Ubicación y contacto van al perfil de la agencia (mismo lugar que
        # edita Admin y que lee el Panel de Agencias): así quedan cargados
        # desde el primer día y Admin ya los muestra completos.
        execute(
            """INSERT INTO agencia_config
               (agencia_id, nombre_agencia, direccion, ciudad, provincia, telefono)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (agencia_id, nombre_agencia, direccion, ciudad, provincia, telefono),
        )
        codigo = crear_codigo(agencia_id)
        enviado = enviar_codigo_email(email, nombre_agencia, codigo)
        session["agencia_pendiente_id"] = agencia_id
        if enviado:
            flash(f"Te mandamos un código de verificación a {email}.", "success")
        else:
            # Sin RESEND_API_KEY configurada todavía: no se manda de
            # verdad, pero el flujo se puede seguir probando -- el código
            # queda en la consola del servidor.
            flash("No se pudo enviar el mail todavía (revisá la consola del servidor para el código).", "error")
        return redirect(url_for("auth.verificar"))
    return render_template("auth/registro.html", prev={}, provincias=PROVINCIAS_AR)


@bp.route("/verificar", methods=["GET", "POST"])
def verificar():
    agencia_id = session.get("agencia_pendiente_id")
    if not agencia_id:
        return redirect(url_for("auth.login"))
    agencia = query("SELECT * FROM agencias WHERE id = ?", (agencia_id,), one=True)
    if not agencia:
        session.pop("agencia_pendiente_id", None)
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        codigo = request.form.get("codigo", "")
        if validar_codigo(agencia_id, codigo):
            session.pop("agencia_pendiente_id", None)
            agencia = query("SELECT * FROM agencias WHERE id = ?", (agencia_id,), one=True)
            _loguear(agencia)
            # Meta Pixel (21/09/2026): CompleteRegistration se dispara recién
            # acá, con el mail ya validado -- no por un parametro de URL como
            # paso en PresupuestoPRO (se perdia al tocar la validacion). La
            # bandera en sesion la consume el context processor
            # _inject_fb_eventos de app.py y se muestra una sola vez en la
            # primera pagina que carga despues (precios.index).
            session["fb_eventos_pendientes"] = ["CompleteRegistration"]
            flash("Cuenta verificada -- ¡bienvenido a AGENCIEROS!", "success")
            return redirect(url_for("precios.index"))
        flash("Código incorrecto o vencido.", "error")

    return render_template("auth/verificar.html", email=agencia["email"])


@bp.route("/verificar/reenviar")
def reenviar_codigo():
    agencia_id = session.get("agencia_pendiente_id")
    if not agencia_id:
        return redirect(url_for("auth.login"))
    agencia = query("SELECT * FROM agencias WHERE id = ?", (agencia_id,), one=True)
    if agencia:
        codigo = crear_codigo(agencia_id)
        enviado = enviar_codigo_email(agencia["email"], agencia["nombre_agencia"], codigo)
        flash(
            "Te mandamos un código nuevo." if enviado
            else "No se pudo reenviar el mail (revisá la consola del servidor para el código).",
            "success" if enviado else "error",
        )
    return redirect(url_for("auth.verificar"))


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
