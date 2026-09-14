import os
import time
from datetime import datetime
from urllib.parse import quote_plus

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify

from database import query, execute
from routes.tasacion import FACTOR_MECANICO, FACTOR_ESTETICO, MARGEN_OBJETIVO

bp = Blueprint("tomas", __name__, url_prefix="/tomas")

# --- Paso 1: datos técnicos ---
PUNTOS = [
    ("motor", "Motor"), ("caja", "Caja"), ("embrague", "Embrague"), ("frenos", "Frenos"),
    ("suspension", "Suspensión"), ("direccion", "Dirección"), ("interior", "Interior"),
    ("tapizados", "Tapizados"), ("cubiertas", "Cubiertas"), ("electricidad", "Electricidad"),
    ("aire_acondicionado", "Aire acondicionado"), ("documentacion", "Documentación"),
]
CALIFICACIONES = ["Excelente", "Bueno", "Regular", "Malo"]
PUNTAJE_CALIFICACION = {"Excelente": 4, "Bueno": 3, "Regular": 2, "Malo": 1}

# --- Paso 2: fotos + inspección visual de chapa ---
VISTAS = [
    ("frente", "Frente"), ("trasera", "Trasera"), ("lateral_izq", "Lateral izquierdo"),
    ("lateral_der", "Lateral derecho"), ("superior", "Vista superior"),
]
TIPOS_DANIO = [
    ("golpe", "Golpe"), ("rayon", "Rayón"), ("vidrio_roto", "Vidrio roto"),
    ("optica", "Óptica"), ("paragolpes", "Paragolpes"), ("abolladura", "Abolladura"),
]
GRAVEDADES = [("leve", "Leve"), ("moderado", "Moderado"), ("grave", "Grave")]
PESO_GRAVEDAD = {"leve": 0.4, "moderado": 0.8, "grave": 1.6}
EXTENSIONES_PERMITIDAS = {"jpg", "jpeg", "png", "webp", "gif"}


def _toma_o_none(toma_id):
    toma = query("SELECT * FROM tomas_vehiculo WHERE id = ?", (toma_id,), one=True)
    if not toma:
        flash("Toma no encontrada.", "error")
    return toma


def _evaluadores():
    """Nombres de evaluador ya usados en tomas anteriores, para sugerir en
    el campo (mismo criterio que Marca/Modelo: se aprende de lo cargado,
    no hace falta un alta aparte de 'evaluadores')."""
    filas = query(
        "SELECT DISTINCT evaluador FROM tomas_vehiculo WHERE evaluador IS NOT NULL AND TRIM(evaluador) != '' ORDER BY evaluador"
    )
    return [f["evaluador"] for f in filas]


def _promedio_a_categoria(promedio):
    if promedio >= 3.5:
        return "Excelente"
    if promedio >= 2.5:
        return "Bueno"
    if promedio >= 1.5:
        return "Regular"
    return "Malo"


def _calcular_estado_mecanico(toma):
    """Sugerencia de estado mecánico a partir de las calificaciones de los
    12 puntos de la Toma técnica (promedio, mapeado a la categoría más
    cercana). Ajustable a mano en el paso de Tasación."""
    valores = [toma[codigo] for codigo, _ in PUNTOS if toma[codigo] in PUNTAJE_CALIFICACION]
    if not valores:
        return "Bueno"
    promedio = sum(PUNTAJE_CALIFICACION[v] for v in valores) / len(valores)
    return _promedio_a_categoria(promedio)


def _calcular_estado_estetico(marcadores):
    """Sugerencia de estado estético a partir de la cantidad y gravedad de
    los daños marcados en la Inspección visual. Sin daños marcados (o sin
    fotos todavía) se sugiere 'Bueno' como punto de partida neutro."""
    if not marcadores:
        return "Bueno"
    descuento = sum(PESO_GRAVEDAD.get(m["gravedad"], 0.5) for m in marcadores)
    promedio = max(1.0, 4.0 - descuento)
    return _promedio_a_categoria(promedio)


def _marcadores_de_toma(toma_id):
    return query(
        """SELECT im.*, iv.vista AS vista FROM inspeccion_marcadores im
           JOIN inspeccion_visual iv ON iv.id = im.inspeccion_visual_id
           WHERE iv.toma_id = ?""",
        (toma_id,),
    )


def _costo_reparacion_sugerido(marcadores):
    """Suma de los costos de reparación cargados en cada daño marcado en la
    Inspección visual — una de las dos fuentes que arman el 'Gastos
    estimados' sugerido en el paso de Tasación (la otra es
    _costo_puntos_tecnicos)."""
    return sum(m["costo_reparacion"] or 0 for m in marcadores)


def _costo_puntos_tecnicos(toma):
    """Suma de los costos de reparación cargados punto por punto en la Toma
    técnica (ej: tapizados en mal estado por suciedad o roturas → costo de
    limpieza/arreglo). La otra fuente que arma el 'Gastos estimados'
    sugerido en Tasación es _costo_reparacion_sugerido (daños visuales)."""
    return sum(toma[f"costo_{codigo}"] or 0 for codigo, _ in PUNTOS)


def _puntos_con_costo(toma):
    """Arma, para cada uno de los 12 puntos técnicos, su calificación, el
    costo de reparación cargado y el comentario (en qué consiste la
    reparación) — lista lista para tabla en los templates."""
    return [
        {
            "codigo": codigo, "label": label, "calificacion": toma[codigo],
            "costo": toma[f"costo_{codigo}"], "comentario": toma[f"comentario_{codigo}"],
        }
        for codigo, label in PUNTOS
    ]


def _puntos_a_reparar(toma):
    """Solo los puntos del Paso 1 que tienen costo de reparación cargado —
    para el resumen de 'qué hay que arreglar' que se muestra en el Paso 3
    (Tasación) antes de calcular."""
    return [p for p in _puntos_con_costo(toma) if p["costo"]]


def _formatear_fecha(iso_str):
    """Convierte el `created_at` de SQLite ('YYYY-MM-DD HH:MM:SS') al formato
    DD/MM/YYYY HH:MM que se muestra en la UI."""
    if not iso_str:
        return ""
    try:
        return datetime.strptime(iso_str, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso_str


def _tasacion_con_extra(tasacion_row):
    """Agrega a una fila de `tasaciones` el % de beneficio (margen esperado
    sobre el precio de toma) y la fecha ya formateada, para no repetir esta
    cuenta en los templates. `riesgo` se sigue guardando en la tabla pero ya
    no se calcula ni se muestra en ningún lado (se sacó del panel de
    Resultado a pedido de Daniel)."""
    if not tasacion_row:
        return None
    t = dict(tasacion_row)
    precio = t.get("precio_max_recomendado") or 0
    margen = t.get("margen_esperado") or 0
    t["porcentaje_beneficio"] = round((margen / precio) * 100, 1) if precio else 0
    t["fecha_fmt"] = _formatear_fecha(t.get("created_at"))
    return t


def _agrupar_danios_por_vista(danios_a_reparar):
    """Agrupa los daños marcados (Paso 2) que tienen costo cargado por
    foto/vista, en el orden de VISTAS — para el panel 'Qué hay que reparar',
    que antes los listaba todos planos sin indicar de qué foto salía cada
    uno."""
    grupos = []
    for codigo, label in VISTAS:
        items = [d for d in danios_a_reparar if d["vista"] == codigo]
        if items:
            grupos.append({
                "vista_codigo": codigo,
                "vista_label": label,
                "items": items,
                "subtotal": sum(d["costo_reparacion"] or 0 for d in items),
            })
    return grupos


def _links_comparables(marca, modelo, version, anio):
    """Búsquedas rápidas de precios de referencia en la web (MercadoLibre,
    RosarioGarage, Facebook Marketplace) para el vehículo de la toma. No
    hacemos scraping automático (es frágil y varios sitios lo bloquean) —
    generamos el link de búsqueda directa a cada sitio (nada de pasar por
    Google) y lo abre el agenciero en una pestaña nueva, para cotejar a ojo
    contra el 'valor de tabla'.

    RosarioGarage no tiene un buscador de texto libre documentado en la UI,
    pero su motor interno sí lo acepta por query string
    (?action=finder/search&itmModelDesc=<texto>) y devuelve resultados reales
    del sitio combinando marca+modelo (probado a mano: "ford focus" -> 6
    avisos de Ford Focus). Facebook Marketplace tiene su propio buscador en
    /marketplace/search/?query=<texto> — como el agenciero ya suele estar
    logueado en su Facebook, entra directo a los resultados en vez de pasar
    por una búsqueda de Google que muchas veces trae resultados viejos o
    de otra ciudad."""
    partes = [p for p in [marca, modelo, version, str(anio) if anio else ""] if p]
    consulta = " ".join(partes).strip()
    if not consulta:
        return []
    slug_ml = quote_plus(consulta).replace("+", "-")
    return [
        {"label": "MercadoLibre", "url": f"https://listado.mercadolibre.com.ar/{slug_ml}"},
        {"label": "RosarioGarage", "url": f"https://www.rosariogarage.com/index.php?action=finder/search&itmModelDesc={quote_plus(consulta)}"},
        {"label": "Facebook Marketplace", "url": f"https://www.facebook.com/marketplace/search/?query={quote_plus(consulta)}"},
    ]


# ---------------------------------------------------------------------------
# Paso 1 · Toma técnica
# ---------------------------------------------------------------------------

@bp.route("/")
def index():
    tomas = query("SELECT * FROM tomas_vehiculo ORDER BY created_at DESC")
    tomas_data = []
    for t in tomas:
        fotos_cargadas = query(
            "SELECT COUNT(*) c FROM inspeccion_visual WHERE toma_id = ? AND imagen_url IS NOT NULL",
            (t["id"],), one=True,
        )["c"]
        tasacion = query(
            "SELECT * FROM tasaciones WHERE toma_id = ? ORDER BY id DESC LIMIT 1", (t["id"],), one=True
        )
        tomas_data.append({"toma": t, "fotos_cargadas": fotos_cargadas, "tasacion": tasacion})
    return render_template("tomas/index.html", tomas_data=tomas_data)


@bp.route("/nueva", methods=["GET", "POST"])
def nueva():
    prefill = {
        "vehiculo_id": request.args.get("vehiculo_id", ""),
        "marca": request.args.get("marca", ""),
        "modelo": request.args.get("modelo", ""),
        "version": request.args.get("version", ""),
        "anio": request.args.get("anio", ""),
    }
    if request.method == "POST":
        f = request.form

        def _costo(codigo):
            valor = f.get(f"costo_{codigo}")
            try:
                return float(valor) if valor else None
            except ValueError:
                return None

        columnas_costo = ", ".join(f"costo_{codigo}" for codigo, _ in PUNTOS)
        placeholders_costo = ", ".join("?" for _ in PUNTOS)
        columnas_comentario = ", ".join(f"comentario_{codigo}" for codigo, _ in PUNTOS)
        placeholders_comentario = ", ".join("?" for _ in PUNTOS)
        toma_id = execute(
            f"""INSERT INTO tomas_vehiculo
               (vehiculo_id, marca, modelo, version, anio, evaluador, motor, caja, embrague, frenos, suspension,
                direccion, interior, tapizados, cubiertas, electricidad, aire_acondicionado,
                documentacion, observaciones, {columnas_costo}, {columnas_comentario})
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,{placeholders_costo},{placeholders_comentario})""",
            (
                f.get("vehiculo_id") or None,
                f.get("marca"), f.get("modelo"), f.get("version"), f.get("anio") or None,
                f.get("evaluador"),
                f.get("motor"), f.get("caja"), f.get("embrague"), f.get("frenos"), f.get("suspension"),
                f.get("direccion"), f.get("interior"), f.get("tapizados"), f.get("cubiertas"),
                f.get("electricidad"), f.get("aire_acondicionado"), f.get("documentacion"),
                f.get("observaciones"),
                *[_costo(codigo) for codigo, _ in PUNTOS],
                *[(f.get(f"comentario_{codigo}") or "").strip() or None for codigo, _ in PUNTOS],
            ),
        )
        flash("Toma registrada. Ahora sumá las fotos y marcá los daños de la carrocería.", "success")
        return redirect(url_for("tomas.inspeccion", toma_id=toma_id))
    return render_template(
        "tomas/form.html", puntos=PUNTOS, calificaciones=CALIFICACIONES, prefill=prefill,
        evaluadores=_evaluadores(),
    )


@bp.route("/api/precio")
def api_precio():
    """Precio de guía (InfoAuto) para Marca+Modelo, tal como se muestra en
    Paso 1 de la Toma apenas hay Modelo cargado — para que el evaluador vea
    de entrada si el vehículo tiene precio de referencia cargado, sin
    esperar a llegar al Paso 3 (Tasación), que ya hace esta misma consulta.
    Con Año puntual, se busca ese año exacto y, si no hay, se cae al año
    más reciente disponible (mejor mostrar algo aproximado que nada)."""
    marca = request.args.get("marca", "")
    modelo = request.args.get("modelo", "")
    version = request.args.get("version", "")
    anio = request.args.get("anio", "")
    if not marca or not modelo:
        return jsonify({"precio": None, "anio": None})

    def _buscar(con_anio):
        sql = "SELECT precio_referencia, anio FROM precios_base WHERE marca = ? AND modelo = ?"
        params = [marca, modelo]
        if version:
            sql += " AND version = ?"
            params.append(version)
        if con_anio and anio:
            sql += " AND anio = ?"
            params.append(anio)
        sql += " ORDER BY anio DESC LIMIT 1"
        return query(sql, tuple(params), one=True)

    row = _buscar(con_anio=True) if anio else _buscar(con_anio=False)
    if not row and anio:
        # No hay precio para ese año puntual: el más reciente disponible
        # sirve como aproximación en vez de no mostrar nada.
        row = _buscar(con_anio=False)
    return jsonify({
        "precio": row["precio_referencia"] if row else None,
        "anio": row["anio"] if row else None,
    })


@bp.route("/<int:toma_id>")
def detalle(toma_id):
    toma = _toma_o_none(toma_id)
    if not toma:
        return redirect(url_for("tomas.index"))
    fotos_cargadas = query(
        "SELECT COUNT(*) c FROM inspeccion_visual WHERE toma_id = ? AND imagen_url IS NOT NULL",
        (toma_id,), one=True,
    )["c"]
    marcadores = _marcadores_de_toma(toma_id)
    tasacion = _tasacion_con_extra(
        query("SELECT * FROM tasaciones WHERE toma_id = ? ORDER BY id DESC LIMIT 1", (toma_id,), one=True)
    )
    return render_template(
        "tomas/detalle.html",
        toma=toma,
        puntos_data=_puntos_con_costo(toma),
        fotos_cargadas=fotos_cargadas,
        total_marcadores=len(marcadores),
        estado_mecanico_sugerido=_calcular_estado_mecanico(toma),
        estado_estetico_sugerido=_calcular_estado_estetico(marcadores),
        costo_puntos_tecnicos=_costo_puntos_tecnicos(toma),
        tasacion=tasacion,
    )


# ---------------------------------------------------------------------------
# Paso 2 · Fotos + inspección visual de chapa
# ---------------------------------------------------------------------------

@bp.route("/<int:toma_id>/inspeccion")
def inspeccion(toma_id):
    toma = _toma_o_none(toma_id)
    if not toma:
        return redirect(url_for("tomas.index"))

    vistas_data = []
    for codigo, label in VISTAS:
        vista_row = query(
            "SELECT * FROM inspeccion_visual WHERE toma_id = ? AND vista = ?", (toma_id, codigo), one=True
        )
        marcadores = []
        if vista_row:
            marcadores = query(
                "SELECT * FROM inspeccion_marcadores WHERE inspeccion_visual_id = ? ORDER BY id",
                (vista_row["id"],),
            )
        vistas_data.append({
            "codigo": codigo,
            "label": label,
            "imagen_url": vista_row["imagen_url"] if vista_row else None,
            "marcadores": marcadores,
            "costo_total": sum(m["costo_reparacion"] or 0 for m in marcadores),
        })

    return render_template(
        "tomas/inspeccion.html",
        toma=toma,
        vistas_data=vistas_data,
        tipos=TIPOS_DANIO,
        gravedades=GRAVEDADES,
        tipos_label=dict(TIPOS_DANIO),
        gravedades_label=dict(GRAVEDADES),
    )


@bp.route("/<int:toma_id>/inspeccion/<vista>/foto", methods=["POST"])
def subir_foto(toma_id, vista):
    toma = _toma_o_none(toma_id)
    if not toma:
        return redirect(url_for("tomas.index"))
    if vista not in dict(VISTAS):
        flash("Vista inválida.", "error")
        return redirect(url_for("tomas.inspeccion", toma_id=toma_id))

    archivo = request.files.get("foto")
    if not archivo or archivo.filename == "":
        flash("Elegí una foto para subir.", "error")
        return redirect(url_for("tomas.inspeccion", toma_id=toma_id))

    ext = archivo.filename.rsplit(".", 1)[-1].lower() if "." in archivo.filename else ""
    if ext not in EXTENSIONES_PERMITIDAS:
        flash("Formato de imagen no soportado (usá JPG, PNG, WEBP o GIF).", "error")
        return redirect(url_for("tomas.inspeccion", toma_id=toma_id))

    carpeta = os.path.join(current_app.root_path, "static", "uploads", "inspeccion", str(toma_id))
    os.makedirs(carpeta, exist_ok=True)
    nombre_archivo = f"{vista}_{int(time.time())}.{ext}"
    archivo.save(os.path.join(carpeta, nombre_archivo))
    imagen_url = url_for("static", filename=f"uploads/inspeccion/{toma_id}/{nombre_archivo}")

    vista_row = query(
        "SELECT * FROM inspeccion_visual WHERE toma_id = ? AND vista = ?", (toma_id, vista), one=True
    )
    if vista_row:
        execute("UPDATE inspeccion_visual SET imagen_url = ? WHERE id = ?", (imagen_url, vista_row["id"]))
    else:
        execute(
            "INSERT INTO inspeccion_visual (toma_id, vista, imagen_url) VALUES (?,?,?)",
            (toma_id, vista, imagen_url),
        )
    flash(f"Foto de '{dict(VISTAS)[vista]}' cargada.", "success")
    return redirect(url_for("tomas.inspeccion", toma_id=toma_id))


@bp.route("/<int:toma_id>/inspeccion/<vista>/marcador", methods=["POST"])
def agregar_marcador(toma_id, vista):
    toma = _toma_o_none(toma_id)
    if not toma:
        return redirect(url_for("tomas.index"))

    vista_row = query(
        "SELECT * FROM inspeccion_visual WHERE toma_id = ? AND vista = ?", (toma_id, vista), one=True
    )
    if not vista_row:
        flash("Subí una foto de esa vista antes de marcar daños.", "error")
        return redirect(url_for("tomas.inspeccion", toma_id=toma_id))

    f = request.form
    try:
        pos_x = float(f.get("pos_x"))
        pos_y = float(f.get("pos_y"))
    except (TypeError, ValueError):
        flash("No se pudo ubicar el marcador sobre la imagen, probá de nuevo.", "error")
        return redirect(url_for("tomas.inspeccion", toma_id=toma_id))

    tipo = f.get("tipo") if f.get("tipo") in dict(TIPOS_DANIO) else "golpe"
    gravedad = f.get("gravedad") if f.get("gravedad") in dict(GRAVEDADES) else "leve"
    descripcion = (f.get("descripcion") or "").strip()
    try:
        costo_reparacion = float(f.get("costo_reparacion")) if f.get("costo_reparacion") else None
    except ValueError:
        costo_reparacion = None

    execute(
        """INSERT INTO inspeccion_marcadores
           (inspeccion_visual_id, pos_x, pos_y, tipo, gravedad, descripcion, costo_reparacion)
           VALUES (?,?,?,?,?,?,?)""",
        (vista_row["id"], pos_x, pos_y, tipo, gravedad, descripcion, costo_reparacion),
    )
    flash("Marcador agregado.", "success")
    return redirect(url_for("tomas.inspeccion", toma_id=toma_id))


@bp.route("/<int:toma_id>/inspeccion/marcador/<int:marcador_id>/eliminar", methods=["POST"])
def eliminar_marcador(toma_id, marcador_id):
    toma = _toma_o_none(toma_id)
    if not toma:
        return redirect(url_for("tomas.index"))
    execute("DELETE FROM inspeccion_marcadores WHERE id = ?", (marcador_id,))
    flash("Marcador eliminado.", "success")
    return redirect(url_for("tomas.inspeccion", toma_id=toma_id))


# ---------------------------------------------------------------------------
# Paso 3 · Tasación
# ---------------------------------------------------------------------------

@bp.route("/<int:toma_id>/tasacion", methods=["GET", "POST"])
def tasacion(toma_id):
    toma = _toma_o_none(toma_id)
    if not toma:
        return redirect(url_for("tomas.index"))

    marcadores = _marcadores_de_toma(toma_id)
    estado_mecanico_sugerido = _calcular_estado_mecanico(toma)
    estado_estetico_sugerido = _calcular_estado_estetico(marcadores)

    precio_base = query(
        """SELECT precio_referencia FROM precios_base
           WHERE marca = ? AND modelo = ? AND (version = ? OR ? IS NULL OR ? = '')
           ORDER BY anio DESC LIMIT 1""",
        (toma["marca"], toma["modelo"], toma["version"], toma["version"], toma["version"]),
        one=True,
    )
    valor_referencia_sugerido = precio_base["precio_referencia"] if precio_base else ""
    costo_puntos_tecnicos = _costo_puntos_tecnicos(toma)
    costo_danios_visuales = _costo_reparacion_sugerido(marcadores)
    gastos_estimados_sugerido = costo_puntos_tecnicos + costo_danios_visuales
    links_comparables = _links_comparables(toma["marca"], toma["modelo"], toma["version"], toma["anio"])
    puntos_a_reparar = _puntos_a_reparar(toma)
    danios_por_vista = _agrupar_danios_por_vista([m for m in marcadores if m["costo_reparacion"]])

    es_nueva = False

    if request.method == "POST":
        f = request.form
        valor_referencia = float(f.get("valor_referencia") or 0)
        estado_mecanico = f.get("estado_mecanico") or estado_mecanico_sugerido
        estado_estetico = f.get("estado_estetico") or estado_estetico_sugerido
        # Los gastos estimados dejaron de ser editables a mano (Daniel pidió
        # sacar ese input): siempre son la suma de los costos ya cargados en
        # el Paso 1 (puntos técnicos) + Paso 2 (daños visuales), que se ve
        # desglosada en el panel "Qué hay que reparar".
        gastos_estimados = gastos_estimados_sugerido

        factor = FACTOR_MECANICO[estado_mecanico] * FACTOR_ESTETICO[estado_estetico]
        valor_ajustado = valor_referencia * factor
        precio_max_recomendado = valor_ajustado - gastos_estimados - (valor_referencia * MARGEN_OBJETIVO)
        margen_esperado = valor_ajustado - precio_max_recomendado - gastos_estimados

        # `riesgo` se sigue calculando y guardando (por si sirve a futuro para
        # el algoritmo de valuación), pero ya no se muestra en el panel de
        # Resultado — Daniel pidió sacarlo de la vista.
        malos = [estado_mecanico, estado_estetico].count("Malo")
        regulares = [estado_mecanico, estado_estetico].count("Regular")
        if malos >= 1 or gastos_estimados > valor_referencia * 0.25:
            riesgo = "Alto"
        elif regulares >= 1:
            riesgo = "Medio"
        else:
            riesgo = "Bajo"

        execute(
            """INSERT INTO tasaciones
               (toma_id, marca, modelo, version, anio, valor_referencia, estado_mecanico, estado_estetico,
                gastos_estimados, precio_max_recomendado, riesgo, margen_esperado)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                toma_id, toma["marca"], toma["modelo"], toma["version"], toma["anio"],
                valor_referencia, estado_mecanico, estado_estetico, gastos_estimados,
                round(precio_max_recomendado), riesgo, round(margen_esperado),
            ),
        )
        flash("Tasación registrada.", "success")
        es_nueva = True

    tasacion_previa = _tasacion_con_extra(
        query("SELECT * FROM tasaciones WHERE toma_id = ? ORDER BY id DESC LIMIT 1", (toma_id,), one=True)
    )

    return render_template(
        "tomas/tasacion.html",
        toma=toma,
        tasacion_previa=tasacion_previa,
        es_nueva=es_nueva,
        opciones=CALIFICACIONES,
        estado_mecanico_sugerido=estado_mecanico_sugerido,
        estado_estetico_sugerido=estado_estetico_sugerido,
        valor_referencia_sugerido=valor_referencia_sugerido,
        gastos_estimados_sugerido=gastos_estimados_sugerido,
        costo_puntos_tecnicos=costo_puntos_tecnicos,
        costo_danios_visuales=costo_danios_visuales,
        links_comparables=links_comparables,
        puntos_a_reparar=puntos_a_reparar,
        danios_por_vista=danios_por_vista,
        vistas_label=dict(VISTAS),
        tipos_label=dict(TIPOS_DANIO),
        gravedades_label=dict(GRAVEDADES),
        form=request.form,
    )
