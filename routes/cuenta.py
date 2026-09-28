"""Mi cuenta (cambiar contraseña) y Usuarios de la agencia (28/09/2026).

- /cuenta/            -> cualquier usuario (y el admin de la plataforma)
                         cambia su propia contraseña.
- /cuenta/usuarios    -> solo el dueño: alta de vendedores/dueños,
                         activar/desactivar, cambiar rol y blanquear clave.
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash

from database import query, execute, get_db, mail_ocupado
from utils.permisos import ROLES

bp = Blueprint("cuenta", __name__, url_prefix="/cuenta")

MIN_CLAVE = 6


def _validar_clave_nueva(nueva, nueva2):
    if len(nueva) < MIN_CLAVE:
        return f"La contraseña nueva tiene que tener al menos {MIN_CLAVE} caracteres."
    if nueva != nueva2:
        return "Las contraseñas nuevas no coinciden."
    return None


@bp.route("/", methods=["GET", "POST"])
def index():
    es_admin = bool(session.get("superadmin_id"))
    if es_admin:
        yo = query("SELECT * FROM plataforma_admins WHERE id = ?", (session["superadmin_id"],), one=True)
    else:
        yo = query("SELECT * FROM agencia_usuarios WHERE id = ? AND agencia_id = ?",
                   (session.get("usuario_id"), session.get("agencia_id")), one=True)
    if not yo:
        flash("No se encontró tu usuario. Volvé a ingresar.", "error")
        return redirect(url_for("auth.logout"))

    if request.method == "POST":
        actual = request.form.get("actual", "")
        nueva = request.form.get("nueva", "")
        nueva2 = request.form.get("nueva2", "")
        if not check_password_hash(yo["password_hash"], actual):
            flash("La contraseña actual no es correcta.", "error")
            return redirect(url_for("cuenta.index"))
        error = _validar_clave_nueva(nueva, nueva2)
        if error:
            flash(error, "error")
            return redirect(url_for("cuenta.index"))
        h = generate_password_hash(nueva)
        if es_admin:
            execute("UPDATE plataforma_admins SET password_hash = ? WHERE id = ?", (h, yo["id"]))
        else:
            execute("UPDATE agencia_usuarios SET password_hash = ? WHERE id = ?", (h, yo["id"]))
            # El mail "de la agencia" queda con la misma clave que su dueño.
            execute("UPDATE agencias SET password_hash = ? WHERE id = ? AND lower(email) = lower(?)",
                    (h, yo["agencia_id"], yo["email"]))
        flash("Listo, tu contraseña quedó cambiada.", "success")
        return redirect(url_for("cuenta.index"))

    return render_template("cuenta/index.html", yo=yo, es_admin=es_admin, roles=ROLES)


def _usuario_de_mi_agencia(usuario_id):
    return query("SELECT * FROM agencia_usuarios WHERE id = ? AND agencia_id = ?",
                 (usuario_id, session["agencia_id"]), one=True)


def _duenos_activos(excepto_id=None):
    fila = query(
        "SELECT COUNT(*) AS c FROM agencia_usuarios WHERE agencia_id = ? AND rol = 'dueno' AND activo = 1 AND id != ?",
        (session["agencia_id"], excepto_id or 0), one=True,
    )
    return fila["c"]


@bp.route("/usuarios")
def usuarios():
    filas = query(
        """SELECT u.*,
                  (SELECT COUNT(*) FROM vehiculos v WHERE v.cargado_por_id = u.id) AS cargados,
                  (SELECT COUNT(*) FROM vehiculos v WHERE v.vendido_por_id = u.id) AS vendidos
           FROM agencia_usuarios u WHERE u.agencia_id = ?
           ORDER BY u.activo DESC, CASE u.rol WHEN 'dueno' THEN 0 ELSE 1 END, u.nombre""",
        (session["agencia_id"],),
    )
    return render_template("cuenta/usuarios.html", usuarios=filas, roles=ROLES, prev={})


@bp.route("/usuarios/nuevo", methods=["POST"])
def usuario_nuevo():
    f = request.form
    nombre = f.get("nombre", "").strip()
    email = f.get("email", "").strip().lower()
    rol = f.get("rol", "vendedor")
    clave = f.get("clave", "")
    error = None
    if not nombre or not email or not clave:
        error = "Completá nombre, mail y contraseña inicial."
    elif "@" not in email:
        error = "El mail no parece válido."
    elif rol not in ROLES:
        error = "Rol inválido."
    elif len(clave) < MIN_CLAVE:
        error = f"La contraseña inicial tiene que tener al menos {MIN_CLAVE} caracteres."
    elif mail_ocupado(get_db(), email):
        error = "Ese mail ya está registrado en AGENCIEROS."
    if error:
        flash(error, "error")
        filas = query("SELECT u.*, 0 AS cargados, 0 AS vendidos FROM agencia_usuarios u WHERE u.agencia_id = ? ORDER BY u.nombre",
                      (session["agencia_id"],))
        return render_template("cuenta/usuarios.html", usuarios=filas, roles=ROLES, prev=f)
    execute(
        "INSERT INTO agencia_usuarios (agencia_id, nombre, email, password_hash, rol) VALUES (?, ?, ?, ?, ?)",
        (session["agencia_id"], nombre, email, generate_password_hash(clave), rol),
    )
    flash(f"Usuario creado: {nombre} ({ROLES[rol]}). Pasale el mail y la contraseña inicial; "
          "después la puede cambiar desde Mi cuenta.", "success")
    return redirect(url_for("cuenta.usuarios"))


@bp.route("/usuarios/<int:usuario_id>", methods=["POST"])
def usuario_editar(usuario_id):
    u = _usuario_de_mi_agencia(usuario_id)
    if not u:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("cuenta.usuarios"))
    accion = request.form.get("accion")
    es_yo = u["id"] == session.get("usuario_id")

    if accion == "rol":
        rol = request.form.get("rol")
        if rol not in ROLES:
            flash("Rol inválido.", "error")
        elif es_yo and rol != "dueno":
            flash("No podés sacarte a vos mismo el rol de dueño.", "error")
        elif u["rol"] == "dueno" and rol != "dueno" and _duenos_activos(excepto_id=u["id"]) == 0:
            flash("La agencia tiene que tener al menos un dueño activo.", "error")
        else:
            execute("UPDATE agencia_usuarios SET rol = ? WHERE id = ?", (rol, u["id"]))
            flash(f"{u['nombre']} ahora es {ROLES[rol]}.", "success")
    elif accion == "nombre":
        nombre = request.form.get("nombre", "").strip()
        if nombre:
            execute("UPDATE agencia_usuarios SET nombre = ? WHERE id = ?", (nombre, u["id"]))
            if es_yo:
                session["usuario_nombre"] = nombre
            flash("Nombre actualizado.", "success")
    elif accion == "activo":
        activar = request.form.get("valor") == "1"
        if not activar and es_yo:
            flash("No podés desactivarte a vos mismo.", "error")
        elif not activar and u["rol"] == "dueno" and _duenos_activos(excepto_id=u["id"]) == 0:
            flash("La agencia tiene que tener al menos un dueño activo.", "error")
        else:
            execute("UPDATE agencia_usuarios SET activo = ? WHERE id = ?", (1 if activar else 0, u["id"]))
            flash(f"{u['nombre']} {'activado' if activar else 'desactivado (ya no puede ingresar)'}.", "success")
    elif accion == "clave":
        clave = request.form.get("clave", "")
        if len(clave) < MIN_CLAVE:
            flash(f"La contraseña tiene que tener al menos {MIN_CLAVE} caracteres.", "error")
        else:
            h = generate_password_hash(clave)
            execute("UPDATE agencia_usuarios SET password_hash = ? WHERE id = ?", (h, u["id"]))
            execute("UPDATE agencias SET password_hash = ? WHERE id = ? AND lower(email) = lower(?)",
                    (h, u["agencia_id"], u["email"]))
            flash(f"Contraseña de {u['nombre']} cambiada. Pasásela y que la cambie desde Mi cuenta.", "success")
    return redirect(url_for("cuenta.usuarios"))
