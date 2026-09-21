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

from storage import uploads_dir

from database import query, execute, obtener_config_agencia

bp = Blueprint("admin", __name__, url_prefix="/admin")

EXTENSIONES_PERMITIDAS_LOGO = {"jpg", "jpeg", "png", "webp"}

# Lista cerrada de provincias argentinas (18/09/2026, Panel de Agencias) --
# select real en vez de texto libre, para que el panel pueda agrupar/filtrar
# agencias por provincia sin duplicados por tipeo ("Bs As" vs "Buenos Aires").
PROVINCIAS_AR = [
    "Buenos Aires", "Ciudad Autónoma de Buenos Aires", "Catamarca", "Chaco",
    "Chubut", "Córdoba", "Corrientes", "Entre Ríos", "Formosa", "Jujuy",
    "La Pampa", "La Rioja", "Mendoza", "Misiones", "Neuquén", "Río Negro",
    "Salta", "San Juan", "San Luis", "Santa Cruz", "Santa Fe",
    "Santiago del Estero", "Tierra del Fuego", "Tucumán",
]


@bp.route("/", methods=["GET", "POST"])
def index():
    agencia_id = session["agencia_id"]

    if request.method == "POST":
        nombre_agencia = request.form.get("nombre_agencia", "").strip() or None
        nombre_contacto = request.form.get("nombre_contacto", "").strip() or None
        direccion = request.form.get("direccion", "").strip() or None
        ciudad = request.form.get("ciudad", "").strip() or None
        provincia = request.form.get("provincia", "").strip() or None
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

        # % de ganancia esperada default para la Tasación (21/09/2026,
        # pedido de Daniel): se carga en Admin como porcentaje (ej. 15
        # para 15%) y se guarda como fracción (0.15) -- mismo formato que
        # ya usaba el MARGEN_OBJETIVO hardcodeado. Vacío = sigue el
        # default de siempre (15%, ver MARGEN_OBJETIVO_DEFAULT en
        # routes/tasacion.py); no bloquea el guardado si no es un número.
        margen_objetivo_form = request.form.get("margen_objetivo_pct", "").strip()
        margen_objetivo_pct = None
        if margen_objetivo_form:
            try:
                margen_objetivo_pct = round(float(margen_objetivo_form) / 100, 4)
            except ValueError:
                flash("El % de ganancia esperada tiene que ser un número (ej: 15).", "error")
                return redirect(url_for("admin.index"))

        config_actual = obtener_config_agencia(agencia_id)
        logo_url = config_actual.get("logo_url")

        archivo = request.files.get("logo")
        if archivo and archivo.filename:
            ext = archivo.filename.rsplit(".", 1)[-1].lower() if "." in archivo.filename else ""
            if ext not in EXTENSIONES_PERMITIDAS_LOGO:
                flash("El logo tiene que ser una imagen JPG, PNG o WEBP.", "error")
                return redirect(url_for("admin.index"))
            carpeta = uploads_dir("agencia")
            os.makedirs(carpeta, exist_ok=True)
            nombre_archivo = f"logo_{uuid.uuid4().hex}.{ext}"
            archivo.save(os.path.join(carpeta, nombre_archivo))
            logo_url = url_for("static", filename=f"uploads/agencia/{nombre_archivo}")

        existe = query("SELECT id FROM agencia_config WHERE agencia_id = ?", (agencia_id,), one=True)
        if existe:
            execute(
                """UPDATE agencia_config
                   SET nombre_agencia = ?, nombre_contacto = ?, logo_url = ?, direccion = ?, ciudad = ?, provincia = ?,
                       telefono = ?, instagram = ?, facebook = ?, sitio_web = ?, margen_objetivo_pct = ?,
                       updated_at = datetime('now')
                   WHERE agencia_id = ?""",
                (
                    nombre_agencia, nombre_contacto, logo_url, direccion, ciudad, provincia,
                    telefono, instagram, facebook, sitio_web, margen_objetivo_pct, agencia_id,
                ),
            )
        else:
            execute(
                """INSERT INTO agencia_config
                   (agencia_id, nombre_agencia, nombre_contacto, logo_url, direccion, ciudad, provincia,
                    telefono, instagram, facebook, sitio_web, margen_objetivo_pct)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    agencia_id, nombre_agencia, nombre_contacto, logo_url, direccion, ciudad, provincia,
                    telefono, instagram, facebook, sitio_web, margen_objetivo_pct,
                ),
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
    # Se muestra como porcentaje (15) aunque se guarde como fracción (0.15)
    # -- MARGEN_OBJETIVO_DEFAULT es el 15% de siempre, para cuando la
    # agencia todavía no cargó nada acá.
    from routes.tasacion import MARGEN_OBJETIVO_DEFAULT
    margen_pct_actual = round(
        (config.get("margen_objetivo_pct") if config.get("margen_objetivo_pct") is not None else MARGEN_OBJETIVO_DEFAULT) * 100,
        2,
    )
    return render_template(
        "admin/index.html", config=config, provincias=PROVINCIAS_AR, margen_pct_actual=margen_pct_actual
    )
