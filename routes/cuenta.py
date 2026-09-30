"""Mi cuenta (cambiar contraseña) y Usuarios de la agencia (28/09/2026).

- /cuenta/            -> cualquier usuario (y el admin de la plataforma)
                         cambia su propia contraseña.
- /cuenta/usuarios    -> solo el dueño: alta de vendedores/dueños,
                         activar/desactivar, cambiar rol y blanquear clave.
- /cuenta/sucursales  -> solo el dueño: sucursales de la agencia (29/09/2026).
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash

from database import query, execute, get_db, mail_ocupado, asignar_existentes_a_sucursal
from utils.permisos import ROLES
from utils.sucursales import sucursales_de, nombres_sucursales

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
    return render_template("cuenta/usuarios.html", usuarios=filas, roles=ROLES, prev={},
                           sucursales=sucursales_de(session["agencia_id"]))


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
        return render_template("cuenta/usuarios.html", usuarios=filas, roles=ROLES, prev=f,
                               sucursales=sucursales_de(session["agencia_id"]))
    execute(
        "INSERT INTO agencia_usuarios (agencia_id, nombre, email, password_hash, rol, sucursal_id) VALUES (?, ?, ?, ?, ?, ?)",
        (session["agencia_id"], nombre, email, generate_password_hash(clave), rol, _sucursal_valida(f.get("sucursal_id"))),
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
    elif accion == "sucursal":
        suc = _sucursal_valida(request.form.get("sucursal_id"))
        execute("UPDATE agencia_usuarios SET sucursal_id = ? WHERE id = ?", (suc, u["id"]))
        nombre_suc = nombres_sucursales(session["agencia_id"]).get(suc)
        flash(f"{u['nombre']}: {'sucursal ' + nombre_suc if nombre_suc else 'sin sucursal fija (ve todas)'}.", "success")
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


def _sucursal_valida(valor):
    """id de una sucursal activa de la agencia logueada, o None."""
    if not valor or not str(valor).isdigit():
        return None
    fila = query("SELECT id FROM sucursales WHERE id = ? AND agencia_id = ? AND activa = 1",
                 (int(valor), session["agencia_id"]), one=True)
    return fila["id"] if fila else None


# ---------------------------------------------------------------------
# Sucursales (29/09/2026, paso 3 de "reorganizar cuentas y Red").
# ---------------------------------------------------------------------
@bp.route("/sucursales")
def sucursales():
    agencia_id = session["agencia_id"]
    filas = query(
        """SELECT s.*,
                  (SELECT COUNT(*) FROM vehiculos v WHERE v.sucursal_id = s.id AND v.agencia_id = s.agencia_id
                     AND v.estado != 'vendido') AS en_stock,
                  (SELECT COUNT(*) FROM vehiculos v WHERE v.sucursal_id = s.id AND v.agencia_id = s.agencia_id
                     AND v.estado = 'vendido') AS vendidos,
                  (SELECT COUNT(*) FROM agencia_usuarios u WHERE u.sucursal_id = s.id AND u.activo = 1) AS usuarios
           FROM sucursales s WHERE s.agencia_id = ?
           ORDER BY s.activa DESC, s.id""",
        (agencia_id,),
    )
    return render_template("cuenta/sucursales.html", sucursales=filas)


def _datos_sucursal(f):
    return (f.get("nombre", "").strip(), f.get("direccion", "").strip() or None,
            f.get("ciudad", "").strip() or None, f.get("telefono", "").strip() or None)


@bp.route("/sucursales/nueva", methods=["POST"])
def sucursal_nueva():
    agencia_id = session["agencia_id"]
    nombre, direccion, ciudad, telefono = _datos_sucursal(request.form)
    if not nombre:
        flash("Poné un nombre para la sucursal (ej: Casa central, Sucursal Funes).", "error")
        return redirect(url_for("cuenta.sucursales"))
    if query("SELECT 1 FROM sucursales WHERE agencia_id = ? AND lower(nombre) = lower(?)", (agencia_id, nombre), one=True):
        flash("Ya hay una sucursal con ese nombre.", "error")
        return redirect(url_for("cuenta.sucursales"))
    es_primera = not query("SELECT 1 FROM sucursales WHERE agencia_id = ?", (agencia_id,), one=True)
    db = get_db()
    cur = db.execute(
        "INSERT INTO sucursales (agencia_id, nombre, direccion, ciudad, telefono) VALUES (?, ?, ?, ?, ?)",
        (agencia_id, nombre, direccion, ciudad, telefono),
    )
    if es_primera:
        asignar_existentes_a_sucursal(db, agencia_id, cur.lastrowid)
    db.commit()
    if es_primera:
        flash(f"Sucursal «{nombre}» creada. Todo lo que ya tenías cargado (stock, ventas, planes y vendedores) "
              "quedó en esta sucursal. Cuando crees la segunda, vas a ver el selector de sucursal en Stock y Dashboard.",
              "success")
    else:
        flash(f"Sucursal «{nombre}» creada. Para pasarle unidades, entrá a cada una en Stock → Editar → Sucursal.", "success")
    return redirect(url_for("cuenta.sucursales"))


@bp.route("/sucursales/<int:sucursal_id>", methods=["POST"])
def sucursal_editar(sucursal_id):
    agencia_id = session["agencia_id"]
    suc = query("SELECT * FROM sucursales WHERE id = ? AND agencia_id = ?", (sucursal_id, agencia_id), one=True)
    if not suc:
        flash("Sucursal no encontrada.", "error")
        return redirect(url_for("cuenta.sucursales"))
    accion = request.form.get("accion")
    if accion == "datos":
        nombre, direccion, ciudad, telefono = _datos_sucursal(request.form)
        if not nombre:
            flash("El nombre no puede quedar vacío.", "error")
        elif query("SELECT 1 FROM sucursales WHERE agencia_id = ? AND lower(nombre) = lower(?) AND id != ?",
                   (agencia_id, nombre, sucursal_id), one=True):
            flash("Ya hay otra sucursal con ese nombre.", "error")
        else:
            execute("UPDATE sucursales SET nombre = ?, direccion = ?, ciudad = ?, telefono = ? WHERE id = ?",
                    (nombre, direccion, ciudad, telefono, sucursal_id))
            flash("Sucursal actualizada.", "success")
    elif accion == "activa":
        activar = request.form.get("valor") == "1"
        if not activar:
            en_stock = query(
                "SELECT COUNT(*) c FROM vehiculos WHERE sucursal_id = ? AND agencia_id = ? AND estado != 'vendido'",
                (sucursal_id, agencia_id), one=True)["c"]
            if en_stock:
                flash(f"«{suc['nombre']}» tiene {en_stock} unidad(es) en stock: pasalas a otra sucursal antes de darla de baja.",
                      "error")
                return redirect(url_for("cuenta.sucursales"))
            execute("UPDATE agencia_usuarios SET sucursal_id = NULL WHERE sucursal_id = ? AND agencia_id = ?",
                    (sucursal_id, agencia_id))
        execute("UPDATE sucursales SET activa = ? WHERE id = ?", (1 if activar else 0, sucursal_id))
        session.pop("suc_sel", None)
        flash(f"«{suc['nombre']}» {'reactivada' if activar else 'dada de baja (lo vendido sigue en los números)'}.", "success")
    return redirect(url_for("cuenta.sucursales"))
