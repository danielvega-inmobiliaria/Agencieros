"""Consultas y avisos de cada agencia al administrador de AGENCIEROS
(28/09/2026, mismo esquema que "Sugerencias" de PresupuestoPRO).

La agencia escribe desde el menú "Consultas y avisos" o desde la Consulta
de precios ("¿No encontrás un precio o te parece distorsionado?"), que
precarga el tipo, el año y el vehículo. Cada mensaje nuevo le llega al
admin por mail y push; el admin los ve en Panel de Agencias → Mensajes.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from database import query, execute
from utils.notificaciones import notificar_admin

bp = Blueprint("mensajes", __name__, url_prefix="/mensajes")

TIPOS = [
    ("precio_falta", "No encuentro un precio"),
    ("precio_distorsionado", "Un precio me parece distorsionado"),
    ("consulta", "Consulta o sugerencia"),
    ("problema", "Algo no funciona"),
]
TIPO_LABEL = dict(TIPOS)


@bp.route("/", methods=["GET", "POST"])
def index():
    agencia_id = session["agencia_id"]
    if request.method == "POST":
        f = request.form
        tipo = f.get("tipo") if f.get("tipo") in TIPO_LABEL else "consulta"
        mensaje = (f.get("mensaje") or "").strip()[:2000]
        anio = (f.get("anio") or "").strip()[:10]
        vehiculo = (f.get("vehiculo") or "").strip()[:200]
        if not mensaje and not vehiculo:
            flash("Escribí tu consulta antes de enviarla.", "error")
            return redirect(url_for("mensajes.index", tipo=tipo, anio=anio, vehiculo=vehiculo))
        execute(
            "INSERT INTO mensajes_admin (agencia_id, tipo, anio, vehiculo, mensaje) VALUES (?, ?, ?, ?, ?)",
            (agencia_id, tipo, anio, vehiculo, mensaje or "(sin comentario)"),
        )
        agencia = query("SELECT nombre_agencia, email, telefono FROM agencias WHERE id = ?", (agencia_id,), one=True)
        detalle = []
        if vehiculo or anio:
            detalle.append(f"Vehículo: {vehiculo} {anio}".strip())
        detalle.append(f"Mensaje: {mensaje or '(sin comentario)'}")
        notificar_admin(
            f"{TIPO_LABEL[tipo]} — {agencia['nombre_agencia']}",
            "\n".join(detalle) + f"\n\nAgencia: {agencia['nombre_agencia']} · {agencia['email']} · {agencia['telefono'] or 'sin teléfono'}",
            ruta="/plataforma/mensajes",
            responder_a=agencia["email"],
        )
        flash("¡Gracias! Tu mensaje le llegó al administrador de AGENCIEROS.", "success")
        return redirect(url_for("mensajes.index"))

    mios = query(
        "SELECT * FROM mensajes_admin WHERE agencia_id = ? ORDER BY created_at DESC LIMIT 50",
        (agencia_id,),
    )
    return render_template(
        "mensajes/index.html",
        mios=mios, tipos=TIPOS, tipo_label=TIPO_LABEL,
        pre={"tipo": request.args.get("tipo", "consulta"), "anio": request.args.get("anio", ""),
             "vehiculo": request.args.get("vehiculo", "")},
    )
