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


def _loguear(agencia, usuario=None):
    # Usuarios por agencia (28/09/2026): la sesión guarda la agencia y,
    # además, qué usuario entró y con qué rol (dueño/vendedor). Si no se
    # pasa usuario (ej. al validar el mail del registro) se usa el dueño
    # con el mail de la agencia.
    if usuario is None:
        usuario = query(
            "SELECT * FROM agencia_usuarios WHERE agencia_id = ? AND lower(email) = lower(?)",
            (agencia["id"], agencia["email"]), one=True,
        ) or query(
            "SELECT * FROM agencia_usuarios WHERE agencia_id = ? AND rol = 'dueno' AND activo = 1 ORDER BY id LIMIT 1",
            (agencia["id"],), one=True,
        )
    session.clear()
    session["agencia_id"] = agencia["id"]
    session["agencia_nombre"] = agencia["nombre_agencia"]
    session["agencia_email"] = agencia["email"]
    if usuario:
        session["usuario_id"] = usuario["id"]
        session["usuario_nombre"] = usuario["nombre"]
        session["usuario_email"] = usuario["email"]
        session["usuario_rol"] = usuario["rol"]
        execute("UPDATE agencia_usuarios SET ultimo_ingreso = datetime('now') WHERE id = ?", (usuario["id"],))


def _loguear_superadmin(admin):
    # Admin de la plataforma (28/09/2026): sesión sin agencia_id, así no
    # puede ver ni cargar datos de negocio de ninguna agencia.
    session.clear()
    session["superadmin_id"] = admin["id"]
    session["superadmin_email"] = admin["email"]
    session["superadmin_nombre"] = admin["nombre"] or "Admin AGENCIEROS"


def _agencia_demo():
    return query("SELECT * FROM agencias WHERE es_demo = 1 ORDER BY id LIMIT 1", one=True)


def _codigo_demo_valido(codigo):
    ag = _agencia_demo()
    return bool(codigo and ag and codigo == (ag["demo_codigo"] or ""))


def _entrar_demo(codigo, visitante_id=None):
    """Loguea en la agencia DEMO. La primera entrada de cada día reinicia
    los datos de ejemplo. `visitante_id` = agencia real (registrada por
    invitación) que está mirando la demo."""
    from demo_agencia import reiniciar_demo, _hoy_ar
    agencia = _agencia_demo()
    vacia = agencia and not query("SELECT 1 FROM vehiculos WHERE agencia_id = ? LIMIT 1", (agencia["id"],), one=True)
    if not agencia or vacia or agencia["demo_reset_at"] != str(_hoy_ar()):
        reiniciar_demo()
        agencia = _agencia_demo()
    usuario = query("SELECT * FROM agencia_usuarios WHERE agencia_id = ? AND rol = 'dueno' ORDER BY id LIMIT 1",
                    (agencia["id"],), one=True)
    _loguear(agencia, usuario)
    session["es_demo"] = True
    session["demo_codigo"] = codigo
    if visitante_id:
        session["demo_visitante_id"] = visitante_id
        execute("UPDATE agencias SET demo_ultimo_ingreso = datetime('now') WHERE id = ?", (visitante_id,))
    return redirect(url_for("dashboard.index"))


@bp.route("/demo")
def demo():
    """Demo por invitación (08/10/2026). El link lleva ?c=CODIGO (se genera y
    renueva desde el Panel de Agencias). Quien lo abre tiene que registrar
    su agencia con todos sus datos y recién ahí entra a la demo; en el Panel
    queda marcado "Por invitación". El administrador entra directo."""
    codigo = (request.args.get("c") or "").strip()
    if not _codigo_demo_valido(codigo):
        return render_template("auth/demo_invitacion.html"), 403
    if session.get("superadmin_id"):
        return _entrar_demo(codigo)
    session["invitacion_demo"] = codigo
    flash("Te invitaron a ver la demo de AGENCIEROS: completá los datos de tu agencia y entrás.", "success")
    return redirect(url_for("auth.registro"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        admin = query("SELECT * FROM plataforma_admins WHERE email = ? AND activo = 1", (email,), one=True)
        if admin and check_password_hash(admin["password_hash"], password):
            _loguear_superadmin(admin)
            return redirect(url_for("plataforma.agencias"))
        # Login por usuario de agencia (28/09/2026). Si el mail no es de
        # ningún usuario (no debería pasar: la migración crea el dueño de
        # cada agencia) se prueba con el mail de la agencia como antes.
        usuario = query("SELECT * FROM agencia_usuarios WHERE lower(email) = ?", (email,), one=True)
        if usuario:
            if not check_password_hash(usuario["password_hash"], password):
                flash("Email o contraseña incorrectos.", "error")
                return render_template("auth/login.html")
            if not usuario["activo"]:
                flash("Tu usuario está desactivado. Consultá con el dueño de la agencia.", "error")
                return render_template("auth/login.html")
            agencia = query("SELECT * FROM agencias WHERE id = ?", (usuario["agencia_id"],), one=True)
        else:
            agencia = query("SELECT * FROM agencias WHERE email = ?", (email,), one=True)
            if not agencia or not check_password_hash(agencia["password_hash"], password):
                flash("Email o contraseña incorrectos.", "error")
                return render_template("auth/login.html")
        if not agencia or not agencia["activo"]:
            flash("Esta cuenta está desactivada.", "error")
            return render_template("auth/login.html")
        if not agencia["email_verificado"] and usuario and usuario["rol"] == "vendedor":
            flash("La agencia todavía no validó su mail. Pedile al dueño que entre primero.", "error")
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
        if agencia["origen"] == "invitacion" and _codigo_demo_valido(agencia["origen_codigo"]):
            return _entrar_demo(agencia["origen_codigo"], agencia["id"])
        _loguear(agencia, usuario)
        return redirect(url_for("precios.index"))
    return render_template("auth/login.html")


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    invitacion = session.get("invitacion_demo") if _codigo_demo_valido(session.get("invitacion_demo")) else None
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
            return render_template("auth/registro.html", prev=request.form, provincias=PROVINCIAS_AR, invitacion=bool(invitacion))
        if not telefono.isdigit() or not 8 <= len(telefono) <= 15:
            flash(
                "El teléfono tiene que tener solo números, con código de área (ej: 3413017371).",
                "error",
            )
            return render_template("auth/registro.html", prev=request.form, provincias=PROVINCIAS_AR, invitacion=bool(invitacion))
        if provincia not in PROVINCIAS_AR:
            flash("Elegí una provincia de la lista.", "error")
            return render_template("auth/registro.html", prev=request.form, provincias=PROVINCIAS_AR, invitacion=bool(invitacion))
        if len(password) < 6:
            flash("La contraseña tiene que tener al menos 6 caracteres.", "error")
            return render_template("auth/registro.html", prev=request.form, provincias=PROVINCIAS_AR, invitacion=bool(invitacion))
        if password != password2:
            flash("Las contraseñas no coinciden.", "error")
            return render_template("auth/registro.html", prev=request.form, provincias=PROVINCIAS_AR, invitacion=bool(invitacion))
        from database import get_db, mail_ocupado
        if mail_ocupado(get_db(), email):
            flash("Ya hay una cuenta registrada con ese email.", "error")
            return render_template("auth/registro.html", prev=request.form, provincias=PROVINCIAS_AR, invitacion=bool(invitacion))

        agencia_id = execute(
            """INSERT INTO agencias
               (nombre_agencia, email, password_hash, telefono, contacto_referencia, email_verificado, activo,
                origen, origen_codigo)
               VALUES (?, ?, ?, ?, ?, 0, 1, ?, ?)""",
            (nombre_agencia, email, generate_password_hash(password), telefono, contacto_referencia,
             "invitacion" if invitacion else "landing", invitacion),
        )
        # Usuario dueño de la agencia (28/09/2026): mismo mail y contraseña.
        execute(
            """INSERT INTO agencia_usuarios (agencia_id, nombre, email, password_hash, rol)
               VALUES (?, ?, ?, ?, 'dueno')""",
            (agencia_id, contacto_referencia, email, generate_password_hash(password)),
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
        # Aviso al admin de la plataforma (28/09/2026): mail + push.
        try:
            from utils.notificaciones import notificar_admin
            notificar_admin(
                f"Nueva agencia registrada{' (POR INVITACIÓN A LA DEMO)' if invitacion else ''}: {nombre_agencia}",
                f"{nombre_agencia} — {ciudad}, {provincia}\nTeléfono: {telefono}\nMail: {email}\n"
                f"Contacto: {contacto_referencia}\n(Falta que valide el código del mail.)",
                ruta=f"/plataforma/agencias/{agencia_id}",
            )
        except Exception as e:
            print(f"[auth] No se pudo avisar al admin del registro: {e}")
        session["agencia_pendiente_id"] = agencia_id
        if enviado:
            flash(f"Te mandamos un código de verificación a {email}.", "success")
        else:
            # Sin RESEND_API_KEY configurada todavía: no se manda de
            # verdad, pero el flujo se puede seguir probando -- el código
            # queda en la consola del servidor.
            flash("No se pudo enviar el mail todavía (revisá la consola del servidor para el código).", "error")
        return redirect(url_for("auth.verificar"))
    return render_template("auth/registro.html", prev={}, provincias=PROVINCIAS_AR, invitacion=bool(invitacion))


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
            if agencia["origen"] == "invitacion" and _codigo_demo_valido(agencia["origen_codigo"]):
                # Registrada por invitación: entra a la demo (sin evento del Pixel).
                flash("Cuenta verificada -- te dejamos recorrer la demo.", "success")
                return _entrar_demo(agencia["origen_codigo"], agencia["id"])
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
