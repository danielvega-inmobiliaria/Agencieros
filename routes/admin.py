"""Admin — datos de perfil de la agencia (17/09/2026).

Logo, nombre comercial, dirección, teléfono y redes -- por ahora es un
único perfil (no hay multi-agencia todavía). Estos datos se usan de cara
al cliente final, por ejemplo en la ficha comercial de Stock
(`stock.ficha`): si están cargados, reemplazan al número de WhatsApp fijo
y muestran el nombre/logo/dirección/redes de la agencia real de Daniel en
vez de datos genéricos.
"""

import os
import uuid

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session

from database import query, execute, obtener_config_agencia

bp = Blueprint("admin", __name__, url_prefix="/admin")

EXTENSIONES_PERMITIDAS_LOGO = {"jpg", "jpeg", "png", "webp"}


@bp.route("/", methods=["GET", "POST"])
def index():
    agencia_id = session["agencia_id"]

    if request.method == "POST":
        nombre_agencia = request.form.get("nombre_agencia", "").strip() or None
        direccion = request.form.get("direccion", "").strip() or None
        telefono = request.form.get("telefono", "").strip() or None
        instagram = request.form.get("instagram", "").strip() or None
        facebook = request.form.get("facebook", "").strip() or None
        sitio_web = request.form.get("sitio_web", "").strip() or None

        if telefono and not telefono.isdigit():
            flash(
                "El teléfono tiene que ser solo números, sin espacios ni guiones "
                "(ej: 5493413017371 -- 549 + código de área + número).",
                "error",
            )
            return redirect(url_for("admin.index"))

        config_actual = obtener_config_agencia(agencia_id)
        logo_url = config_actual.get("logo_url")

        archivo = request.files.get("logo")
        if archivo and archivo.filename:
            ext = archivo.filename.rsplit(".", 1)[-1].lower() if "." in archivo.filename else ""
            if ext not in EXTENSIONES_PERMITIDAS_LOGO:
                flash("El logo tiene que ser una imagen JPG, PNG o WEBP.", "error")
                return redirect(url_for("admin.index"))
            carpeta = os.path.join(current_app.root_path, "static", "uploads", "agencia")
            os.makedirs(carpeta, exist_ok=True)
            nombre_archivo = f"logo_{uuid.uuid4().hex}.{ext}"
            archivo.save(os.path.join(carpeta, nombre_archivo))
            logo_url = url_for("static", filename=f"uploads/agencia/{nombre_archivo}")

        existe = query("SELECT id FROM agencia_config WHERE agencia_id = ?", (agencia_id,), one=True)
        if existe:
            execute(
                """UPDATE agencia_config
                   SET nombre_agencia = ?, logo_url = ?, direccion = ?, telefono = ?,
                       instagram = ?, facebook = ?, sitio_web = ?, updated_at = datetime('now')
                   WHERE agencia_id = ?""",
                (nombre_agencia, logo_url, direccion, telefono, instagram, facebook, sitio_web, agencia_id),
            )
        else:
            execute(
                """INSERT INTO agencia_config
                   (agencia_id, nombre_agencia, logo_url, direccion, telefono, instagram, facebook, sitio_web)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (agencia_id, nombre_agencia, logo_url, direccion, telefono, instagram, facebook, sitio_web),
            )

        # El nombre comercial de Admin es también el que se muestra en el
        # menú y en Red de Agencieros -- si lo cambió acá, se actualiza
        # también en `agencias` y en la sesión actual para que se vea
        # reflejado ya mismo, sin tener que volver a loguearse.
        if nombre_agencia:
            execute("UPDATE agencias SET nombre_agencia = ? WHERE id = ?", (nombre_agencia, agencia_id))
            session["agencia_nombre"] = nombre_agencia

        flash("Datos de la agencia guardados.", "success")
        return redirect(url_for("admin.index"))

    config = obtener_config_agencia(agencia_id)
    return render_template("admin/index.html", config=config)
