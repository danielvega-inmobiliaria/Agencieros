import os
import time
from datetime import datetime
from urllib.parse import quote_plus

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify

from database import query, execute
from routes.tasacion import FACTOR_MECANICO, FACTOR_ESTETICO, MARGEN_OBJETIVO
from storage import uploads_dir

bp = Blueprint("tomas", __name__, url_prefix="/tomas")

# --- Paso 1: datos técnicos ---
# Checklist ampliado 15/09/2026 a partir de la planilla física de peritaje
# que compartió Daniel (SAKURA, 44 puntos totales), y reordenado/reagrupado
# el mismo día (continuación 30) según la planilla Excel que Daniel devolvió
# marcada: "Interior" se retira del checklist por redundante con
# Habitáculo/Tapicería (columna se deja en la tabla sin usar, para no perder
# el historial de tomas ya cargadas); Batería, Documentación, Electricidad y
# Aire acondicionado pasan del grupo Mecánica a Accesorios y equipamiento;
# "Cubiertas" pasó de ser un solo punto a 5 (una por posición + auxilio).
# Los códigos de los puntos que ya existían no se tocan.
GRUPO_MECANICA = [
    ("motor", "Motor"), ("caja", "Caja"), ("distribucion", "Distribución"),
    ("embrague", "Embrague"), ("tren_delantero", "Tren delantero"), ("direccion", "Dirección"),
    ("suspension", "Suspensión"), ("frenos", "Frenos"), ("linea_escape", "Línea de escape"),
    ("chapa", "Chapa"), ("pintura", "Pintura"), ("tapizados", "Tapicería"),
    ("habitaculo", "Habitáculo"),
]
GRUPO_CUBIERTAS = [
    ("cubierta_del_der", "Cubierta delantera derecha"), ("cubierta_del_izq", "Cubierta delantera izquierda"),
    ("cubierta_tras_der", "Cubierta trasera derecha"), ("cubierta_tras_izq", "Cubierta trasera izquierda"),
    ("cubierta_auxilio", "Auxilio"),
]
GRUPO_ACCESORIOS = [
    ("bateria", "Batería"), ("documentacion", "Documentación"), ("electricidad", "Electricidad (general)"),
    ("aire_acondicionado", "Aire acondicionado"),
    ("luces", "Luces"), ("levantavidrios", "Levantavidrios"), ("espejos_electricos", "Espejos eléctricos"),
    ("techo_corredizo", "Techo corredizo"), ("limpia_parabrisas", "Limpiaparabrisas"), ("parabrisas", "Parabrisas"),
    ("luneta_termica", "Luneta térmica"), ("cierre_electrico", "Cierre eléctrico"),
    ("reg_altura_faros", "Regulación de altura de faros"), ("calefactor", "Calefactor"),
    ("computadora_reloj", "Computadora / reloj"), ("control_satelital", "Control satelital"),
    ("parlantes", "Parlantes"), ("cinturones_seguridad", "Cinturones de seguridad"),
    ("criket", "Criket (gato)"), ("llave_ruedas", "Llave de ruedas"), ("manuales", "Manuales"),
    ("duplicado_llave", "Duplicado de llave"), ("radio_cd_usb", "Radio / CD / USB"),
    ("camara_retrovisora", "Cámara retrovisora"), ("sensores_estacionamiento", "Sensores de estacionamiento"),
]
PUNTOS = GRUPO_MECANICA + GRUPO_CUBIERTAS + GRUPO_ACCESORIOS
GRUPOS_PUNTOS = [
    ("Mecánica y carrocería", GRUPO_MECANICA),
    ("Cubiertas", GRUPO_CUBIERTAS),
    ("Accesorios y equipamiento", GRUPO_ACCESORIOS),
]
# Escala de cada punto del checklist — cambiada 15/09/2026 (continuación 30)
# de Excelente/Bueno/Regular/Malo a Bueno/Regular/Malo/No posee (para
# accesorios que el auto directamente no tiene, ej. Control satelital,
# Techo corredizo). "" sigue existiendo como "Sin evaluar" pero ya no es el
# valor por default: todos los puntos arrancan preseleccionados en "Bueno"
# (antes arrancaban en blanco y había que tocar los 44 a mano) — pedido de
# Daniel: "Al empezar a cargar todos los puntos aparecen en Bueno".
CALIFICACIONES_PUNTO = ["Bueno", "Regular", "Malo", "No posee"]
PUNTAJE_CALIFICACION = {"Bueno": 3, "Regular": 2, "Malo": 1}

# Escala del estado mecánico/estético GENERAL del vehículo en el Paso 3
# (Tasación) — a diferencia de CALIFICACIONES_PUNTO, esta es una apreciación
# de conjunto (no punto por punto) y sigue admitiendo "Excelente", que ya no
# está disponible por punto pero sí tiene sentido como promedio general.
CALIFICACIONES = ["Excelente", "Bueno", "Regular", "Malo"]

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


def _texto_reparaciones_pendientes(puntos_a_reparar, danios_por_vista, tipos_label, gravedades_label):
    """Arma un resumen en texto plano de todo lo que hay que reparar (Paso 1
    + Paso 2), para precargar el campo Observaciones del alta en Stock —
    así no hay que volver a tipear a mano lo que ya se cargó en la Toma
    técnica al usar el botón "Agregar a Stock" de la Tasación (pedido de
    Daniel 15/09/2026, continuación 29)."""
    lineas = []
    for p in puntos_a_reparar:
        linea = f"{p['label']} ({p['calificacion']})"
        if p["comentario"]:
            linea += f": {p['comentario']}"
        linea += f" · ${p['costo']:,.0f}".replace(",", ".")
        lineas.append(linea)
    for g in danios_por_vista:
        for d in g["danios"]:
            tipo = tipos_label.get(d["tipo"], d["tipo"])
            gravedad = gravedades_label.get(d["gravedad"], d["gravedad"])
            linea = f"{g['vista_label']} — {tipo} ({gravedad})"
            if d["descripcion"]:
                linea += f": {d['descripcion']}"
            linea += f" · ${d['costo_reparacion']:,.0f}".replace(",", ".")
            lineas.append(linea)
    if not lineas:
        return ""
    return "Pendiente de reparar (según Toma técnica / Tasación):\n- " + "\n- ".join(lineas)


def _texto_equipamiento(toma):
    """Arma, a partir de los puntos evaluados del grupo 'Accesorios y
    equipamiento' del Paso 1 (los 25 puntos de GRUPO_ACCESORIOS: luces,
    espejos eléctricos, aire acondicionado, radio, etc.), un resumen listo
    para precargar el campo Equipamiento del alta en Stock -- para no tener
    que volver a tipear a mano lo que ya se cargó en la Toma técnica
    (pedido de Daniel 16/09/2026: "en equipamiento tiene que precargar todo
    lo cargado en Toma"). Incluye TODOS los puntos evaluados del grupo, no
    solo los que tienen costo cargado (a diferencia de
    _texto_reparaciones_pendientes, que sí filtra por costo) -- acá el
    objetivo es describir qué equipamiento tiene el auto, no qué hay que
    reparar."""
    lineas = []
    for codigo, label in GRUPO_ACCESORIOS:
        calificacion = toma[codigo]
        if not calificacion:
            continue
        linea = f"{label} ({calificacion})"
        comentario = toma[f"comentario_{codigo}"]
        if comentario:
            linea += f": {comentario}"
        lineas.append(linea)
    return "\n".join(lineas)


def _url_agregar_a_stock(toma, tasacion_previa, puntos_a_reparar, danios_por_vista, tipos_label, gravedades_label):
    """Arma el link del botón "Agregar a Stock" del Paso 3 (Tasación), con
    Marca/Modelo/Versión/Año, el precio de tabla, el precio máximo
    recomendado (como punto de partida de "Valor de compra"), los gastos
    estimados y un resumen de reparaciones pendientes ya precargados en el
    alta de Stock — Km/Combustible/Caja/Color/Dominio no se piden en la
    Toma, así que quedan para completar ahí (pedido de Daniel 15/09/2026,
    continuación 29: antes terminar la Tasación no dejaba rastro ninguno en
    Stock)."""
    return url_for(
        "stock.nuevo",
        marca=toma["marca"] or "",
        modelo=toma["modelo"] or "",
        version=toma["version"] or "",
        anio=toma["anio"] or "",
        precio_referencia=tasacion_previa.get("valor_referencia") or "",
        valor_compra=tasacion_previa.get("precio_max_recomendado") or "",
        gastos=tasacion_previa.get("gastos_estimados") or "",
        observaciones=_texto_reparaciones_pendientes(puntos_a_reparar, danios_por_vista, tipos_label, gravedades_label),
        equipamiento=_texto_equipamiento(toma),
        # Para que stock.nuevo pueda linkear de vuelta esta Toma al vehículo
        # que se cree -- si no, la Toma queda huérfana (sin vehiculo_id) aun
        # cuando el auto ya está en Stock (pedido de Daniel 17/09/2026).
        toma_id_origen=toma["id"],
    )


def datos_alta_stock_de_toma(toma_id):
    """Datos que precarga el botón "Agregar a Stock" de una Toma con Tasación
    (marca/modelo/versión/año, valor de compra, gastos, reparaciones pendientes,
    equipamiento y `toma_id_origen`), como dict. None si la Toma no existe,
    no tiene Tasación o ya está vinculada a un vehículo. Lo usa la permuta que
    ingresa a Stock (stock.permuta_destino) para no volver a tipear lo ya
    cargado en la Toma."""
    from urllib.parse import urlparse, parse_qsl
    toma = query("SELECT * FROM tomas_vehiculo WHERE id = ?", (toma_id,), one=True)
    if not toma or toma["vehiculo_id"]:
        return None
    tasacion = _tasacion_con_extra(
        query("SELECT * FROM tasaciones WHERE toma_id = ? ORDER BY id DESC LIMIT 1", (toma_id,), one=True)
    )
    if not tasacion:
        return None
    marcadores = _marcadores_de_toma(toma_id)
    url = _url_agregar_a_stock(
        toma, tasacion, _puntos_a_reparar(toma),
        _agrupar_danios_por_vista([m for m in marcadores if m["costo_reparacion"]]),
        dict(TIPOS_DANIO), dict(GRAVEDADES),
    )
    return dict(parse_qsl(urlparse(url).query))


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
                # OJO: la clave NO puede llamarse "items" — en Jinja, `g.items`
                # sobre un dict resuelve al método dict.items() (built-in)
                # antes que a esta clave, y romper con
                # "'builtin_function_or_method' object is not iterable" al
                # iterarlo sin llamarlo. Por eso "danios" en vez de "items".
                "danios": items,
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
    # Una vez que el auto de una Toma ya está en Stock, seguir viéndola acá
    # no aporta -- para cambiar precio o financiación se edita directo en
    # Stock (pedido de Daniel 17/09/2026). Por default se esconden esas y
    # queda una pestaña aparte ("En Stock") para consultarlas igual, mismo
    # criterio que ya se usa en Stock con la pestaña Vendido.
    vista = request.args.get("vista", "pendientes")
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
        ya_en_stock = False
        if t["vehiculo_id"]:
            ya_en_stock = query("SELECT 1 FROM vehiculos WHERE id = ?", (t["vehiculo_id"],), one=True) is not None
        tomas_data.append({
            "toma": t, "fotos_cargadas": fotos_cargadas, "tasacion": tasacion, "ya_en_stock": ya_en_stock,
        })

    en_stock_count = sum(1 for d in tomas_data if d["ya_en_stock"])
    pendientes_count = len(tomas_data) - en_stock_count
    if vista == "en_stock":
        tomas_mostradas = [d for d in tomas_data if d["ya_en_stock"]]
    else:
        vista = "pendientes"
        tomas_mostradas = [d for d in tomas_data if not d["ya_en_stock"]]

    return render_template(
        "tomas/index.html",
        tomas_data=tomas_mostradas,
        vista=vista,
        pendientes_count=pendientes_count,
        en_stock_count=en_stock_count,
    )


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

        # Columnas dinámicas para los 44 puntos (calificación + costo +
        # comentario de cada uno) — ya no se puede hardcodear una por una en
        # el INSERT como cuando eran 12.
        columnas_base = ", ".join(codigo for codigo, _ in PUNTOS)
        placeholders_base = ", ".join("?" for _ in PUNTOS)
        columnas_costo = ", ".join(f"costo_{codigo}" for codigo, _ in PUNTOS)
        placeholders_costo = ", ".join("?" for _ in PUNTOS)
        columnas_comentario = ", ".join(f"comentario_{codigo}" for codigo, _ in PUNTOS)
        placeholders_comentario = ", ".join("?" for _ in PUNTOS)
        # "¿Código de falla?" / "¿Último service realizado?" pasaron de texto
        # libre a Sí/No + comentario condicional (mismo criterio que los
        # puntos del checklist) — el comentario solo se guarda si la
        # respuesta es "Sí" (pedido de Daniel 15/09/2026, continuación 30).
        tiene_codigo_falla = f.get("tiene_codigo_falla", "No")
        tuvo_ultimo_service = f.get("tuvo_ultimo_service", "No")

        toma_id = execute(
            f"""INSERT INTO tomas_vehiculo
               (vehiculo_id, marca, modelo, version, anio, evaluador,
                tiene_codigo_falla, codigo_falla, tuvo_ultimo_service, ultimo_service,
                observaciones, {columnas_base}, {columnas_costo}, {columnas_comentario})
               VALUES (?,?,?,?,?,?,?,?,?,?,?,{placeholders_base},{placeholders_costo},{placeholders_comentario})""",
            (
                f.get("vehiculo_id") or None,
                f.get("marca"), f.get("modelo"), f.get("version"), f.get("anio") or None,
                f.get("evaluador"),
                tiene_codigo_falla, (f.get("codigo_falla") or None) if tiene_codigo_falla == "Si" else None,
                tuvo_ultimo_service, (f.get("ultimo_service") or None) if tuvo_ultimo_service == "Si" else None,
                f.get("observaciones"),
                *[f.get(codigo) or None for codigo, _ in PUNTOS],
                *[_costo(codigo) for codigo, _ in PUNTOS],
                *[(f.get(f"comentario_{codigo}") or "").strip() or None for codigo, _ in PUNTOS],
            ),
        )
        flash("Toma registrada. Ahora sumá las fotos y marcá los daños de la carrocería.", "success")
        return redirect(url_for("tomas.inspeccion", toma_id=toma_id))
    return render_template(
        "tomas/form.html", grupos_puntos=GRUPOS_PUNTOS, calificaciones_punto=CALIFICACIONES_PUNTO, prefill=prefill,
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
    # Mismo botón "Agregar a Stock" / "Ver en Stock" que ya existía en el
    # Paso 3 dentro de /tomas/<id>/tasacion — replicado acá para que también
    # se vea desde la ficha de la toma (Daniel no lo encontraba ahí, pedido
    # 16/09/2026: antes solo aparecía si se entraba a "Volver a tasar").
    url_agregar_a_stock = None
    label_agregar_a_stock = None
    if tasacion and toma["vehiculo_id"]:
        url_agregar_a_stock = url_for("stock.detalle", vehiculo_id=toma["vehiculo_id"])
        label_agregar_a_stock = "Ver en Stock"
    elif tasacion:
        puntos_a_reparar = _puntos_a_reparar(toma)
        danios_por_vista = _agrupar_danios_por_vista([m for m in marcadores if m["costo_reparacion"]])
        url_agregar_a_stock = _url_agregar_a_stock(
            toma, tasacion, puntos_a_reparar, danios_por_vista,
            dict(TIPOS_DANIO), dict(GRAVEDADES),
        )
        label_agregar_a_stock = "Agregar a Stock"
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
        url_agregar_a_stock=url_agregar_a_stock,
        label_agregar_a_stock=label_agregar_a_stock,
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

    carpeta = uploads_dir("inspeccion", str(toma_id))
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
    # Si la Toma partió de un vehículo que ya estaba en Stock (re-tasación),
    # no hay que crear uno nuevo — se linkea al que ya existe. Si es un
    # vehículo todavía sin cargar, el botón arma el alta prellenada.
    url_agregar_a_stock = None
    label_agregar_a_stock = None
    if tasacion_previa and toma["vehiculo_id"]:
        url_agregar_a_stock = url_for("stock.detalle", vehiculo_id=toma["vehiculo_id"])
        label_agregar_a_stock = "Ver en Stock"
    elif tasacion_previa:
        url_agregar_a_stock = _url_agregar_a_stock(
            toma, tasacion_previa, puntos_a_reparar, danios_por_vista,
            dict(TIPOS_DANIO), dict(GRAVEDADES),
        )
        label_agregar_a_stock = "Agregar a Stock"

    return render_template(
        "tomas/tasacion.html",
        toma=toma,
        tasacion_previa=tasacion_previa,
        url_agregar_a_stock=url_agregar_a_stock,
        label_agregar_a_stock=label_agregar_a_stock,
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
