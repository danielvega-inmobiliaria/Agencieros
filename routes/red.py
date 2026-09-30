"""Red de Agencieros (multi-tenant real desde 18/09/2026): cartelera
compartida entre TODAS las agencias registradas -- cualquiera logueada ve
las publicaciones de las demás, pero solo puede crear/cerrar las suyas
propias (filtro por `agencia_id` de la sesión, no por el texto libre que
antes era `agencia_nombre`)."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort

from database import query, execute, obtener_config_agencia
from buscador import parsear_filtros, condiciones_sql

bp = Blueprint("red", __name__, url_prefix="/red")


def _contacto_publicacion(agencia_id):
    """Nombre de contacto + teléfono para publicar en la Red -- ya no se
    tipean a mano (21/09/2026, pedido de Daniel: "Nombre Contacto y
    Teléfono se cargan solos"). Devuelve (nombre, telefono, texto):
    - nombre: `agencia_config.nombre_contacto` (la persona a la que llamar,
      cargada en Admin) si está completo; si no, el nombre comercial de la
      agencia como respaldo (mejor eso que dejarlo vacío).
    - telefono: el WhatsApp comercial cargado en Admin
      (`agencia_config.telefono`) si está cargado; si no, el teléfono de
      registro de la cuenta (`agencias.telefono`).
    - texto: los dos juntos, listo para guardar en `red_publicaciones.contacto`."""
    config = obtener_config_agencia(agencia_id)
    nombre = config.get("nombre_contacto")
    if not nombre:
        agencia = query("SELECT nombre_agencia FROM agencias WHERE id = ?", (agencia_id,), one=True)
        nombre = agencia["nombre_agencia"] if agencia else None
    telefono = config.get("telefono")
    if not telefono:
        fila = query("SELECT telefono FROM agencias WHERE id = ?", (agencia_id,), one=True)
        telefono = fila["telefono"] if fila else None
    if nombre and telefono:
        texto = f"{nombre} · {telefono}"
    else:
        texto = nombre or telefono
    return nombre, telefono, texto


@bp.route("/")
def index():
    tipo_filtro = request.args.get("tipo", "todos")
    filtros = parsear_filtros(request.args)
    rp = "red_publicaciones."
    condiciones, params = condiciones_sql(filtros, campo_precio="precio", campo_km="km",
                                          campo_marca=rp + "marca", campo_modelo=rp + "modelo",
                                          campo_version=rp + "version", campo_anio=rp + "anio")
    condiciones.append("red_publicaciones.estado = 'activo'")
    if tipo_filtro in ("ofrezco", "busco"):
        condiciones.append("red_publicaciones.tipo = ?")
        params.append(tipo_filtro)
    where = " WHERE " + " AND ".join(condiciones)
    publicaciones = query(
        f"""SELECT red_publicaciones.*, v.estado AS vehiculo_estado, v.id AS vid
            FROM red_publicaciones LEFT JOIN vehiculos v ON v.id = red_publicaciones.vehiculo_id
            {where}
            ORDER BY red_publicaciones.created_at DESC""", tuple(params))
    return render_template(
        "red/index.html",
        publicaciones=publicaciones,
        tipo_filtro=tipo_filtro,
        filtros=filtros,
        mostrar_km=True,
        filtro_tab_nombre="tipo",
        filtro_tab_valor=tipo_filtro,
        limpiar_url=url_for("red.index", tipo=tipo_filtro),
        mi_agencia_id=session.get("agencia_id"),
    )


@bp.route("/nueva", methods=["GET", "POST"])
def nueva():
    agencia_id = session.get("agencia_id")
    # Contacto (21/09/2026): ya no se tipea a mano -- sale solo de Admin/
    # registro (ver `_contacto_publicacion`), igual que el nombre de
    # agencia ya salía de la cuenta logueada.
    nombre_contacto, telefono_contacto, contacto = _contacto_publicacion(agencia_id)
    if request.method == "POST":
        f = request.form
        # El nombre de agencia ya no se tipea a mano -- se toma de la
        # cuenta logueada, así una agencia no puede publicar haciéndose
        # pasar por otra.
        agencia_nombre = session.get("agencia_nombre", "")
        if f.get("tipo") != "busco":
            # Límite de publicaciones del plan (30/09/2026): solo lo que se ofrece.
            from utils.planes import puede_agregar
            permitido, msg = puede_agregar(agencia_id, "red")
            if not permitido:
                flash(msg, "error")
                return redirect(url_for("red.index"))
        execute(
            """INSERT INTO red_publicaciones
               (agencia_id, agencia_nombre, tipo, marca, modelo, version, anio, km, precio, descripcion, contacto)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                agencia_id, agencia_nombre, f.get("tipo"), f.get("marca"), f.get("modelo"),
                f.get("version"), f.get("anio") or None, f.get("km") or None,
                float(f.get("precio") or 0) or None,
                f.get("descripcion"), contacto,
            ),
        )
        flash("Publicación creada en la Red de Agencieros.", "success")
        return redirect(url_for("red.index"))
    return render_template("red/form.html", contacto=contacto)


@bp.route("/<int:pub_id>/cerrar")
def cerrar(pub_id):
    publicacion = query("SELECT * FROM red_publicaciones WHERE id = ?", (pub_id,), one=True)
    if not publicacion:
        abort(404)
    # El admin de la plataforma puede cerrar cualquier publicación (moderación).
    if publicacion["agencia_id"] != session.get("agencia_id") and not session.get("superadmin_id"):
        flash("Esa publicación no es de tu agencia -- no la podés cerrar.", "error")
        return redirect(url_for("red.index"))
    execute("UPDATE red_publicaciones SET estado = 'cerrado' WHERE id = ?", (pub_id,))
    flash("Publicación cerrada.", "success")
    return redirect(url_for("red.index"))


# ---------------------------------------------------------------------
# Unidades de Stock en la Red (paso 4, 28/09/2026). Criterio de Daniel:
# al señar la publicación sigue en la Red marcada "Señado"; se da de baja
# sola solo al vender (si se cancela la seña vuelve a verse Disponible,
# porque el estado se toma siempre del vehículo).
# ---------------------------------------------------------------------
def publicacion_de_vehiculo(vehiculo_id):
    return query(
        "SELECT * FROM red_publicaciones WHERE vehiculo_id = ? AND estado = 'activo' ORDER BY id DESC LIMIT 1",
        (vehiculo_id,), one=True,
    )


def publicar_vehiculo(vehiculo):
    agencia_id = vehiculo["agencia_id"]
    _, _, contacto = _contacto_publicacion(agencia_id)
    agencia = query("SELECT nombre_agencia FROM agencias WHERE id = ?", (agencia_id,), one=True)
    return execute(
        """INSERT INTO red_publicaciones
           (agencia_id, agencia_nombre, tipo, marca, modelo, version, anio, km, precio, descripcion, contacto, vehiculo_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (agencia_id, agencia["nombre_agencia"] if agencia else session.get("agencia_nombre", ""), "ofrezco",
         vehiculo["marca"], vehiculo["modelo"], vehiculo["version"], vehiculo["anio"], vehiculo["km"],
         vehiculo["valor_publicado"] or None, None, contacto, vehiculo["id"]),
    )


def cerrar_red_de_vehiculo(vehiculo_id):
    """Se llama al vender la unidad (Stock, Editar y Financiación)."""
    execute("UPDATE red_publicaciones SET estado = 'cerrado' WHERE vehiculo_id = ? AND estado = 'activo'",
            (vehiculo_id,))


# ---------------------------------------------------------------------
# Pedidos en la Red (29/09/2026, pedido de Daniel): si un pedido no tiene
# ninguna coincidencia, se puede publicar la búsqueda en la Red ("Busca").
# Sin datos del cliente: solo el vehículo buscado y el contacto de la agencia.
# Se da de baja sola al resolver o cancelar el pedido.
# ---------------------------------------------------------------------
def publicacion_de_pedido(pedido_id):
    return query(
        "SELECT * FROM red_publicaciones WHERE pedido_id = ? AND estado = 'activo' ORDER BY id DESC LIMIT 1",
        (pedido_id,), one=True,
    )


def publicar_pedido(pedido):
    agencia_id = pedido["agencia_id"]
    _, _, contacto = _contacto_publicacion(agencia_id)
    agencia = query("SELECT nombre_agencia FROM agencias WHERE id = ?", (agencia_id,), one=True)
    partes = []
    if pedido["anio_desde"] or pedido["anio_hasta"]:
        if pedido["anio_desde"] and pedido["anio_hasta"] and pedido["anio_desde"] != pedido["anio_hasta"]:
            partes.append(f"Año {pedido['anio_desde']} a {pedido['anio_hasta']}")
        else:
            partes.append(f"Año {pedido['anio_desde'] or pedido['anio_hasta']}")
    forma = {"contado": "Paga contado", "cuotas": "Busca financiación", "permuta": "Entrega permuta"}.get(pedido["forma_pago"])
    if forma:
        partes.append(forma)
    return execute(
        """INSERT INTO red_publicaciones
           (agencia_id, agencia_nombre, tipo, marca, modelo, version, anio, precio, descripcion, contacto, pedido_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (agencia_id, agencia["nombre_agencia"] if agencia else session.get("agencia_nombre", ""), "busco",
         pedido["marca"], pedido["modelo"], pedido["version"], pedido["anio_desde"] or pedido["anio_hasta"],
         pedido["precio_maximo"] or None, " · ".join(partes) or None, contacto, pedido["id"]),
    )


def cerrar_red_de_pedido(pedido_id):
    execute("UPDATE red_publicaciones SET estado = 'cerrado' WHERE pedido_id = ? AND estado = 'activo'", (pedido_id,))
