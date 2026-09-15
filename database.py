import os
import sqlite3
from datetime import date
from flask import g
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "agencieros.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    nombre TEXT,
    agencia_nombre TEXT,
    is_admin INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vehiculos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marca TEXT NOT NULL,
    modelo TEXT NOT NULL,
    version TEXT,
    anio INTEGER,
    km INTEGER,
    combustible TEXT,
    caja TEXT,
    color TEXT,
    dominio TEXT,
    estado TEXT NOT NULL DEFAULT 'disponible',
    equipamiento TEXT,
    observaciones TEXT,
    documentacion TEXT,
    valor_compra REAL DEFAULT 0,
    gastos REAL DEFAULT 0,
    valor_publicado REAL DEFAULT 0,
    valor_vendido REAL,
    fecha_ingreso TEXT DEFAULT (date('now')),
    fecha_venta TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vehiculo_fotos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehiculo_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    orden INTEGER DEFAULT 0,
    FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id)
);

CREATE TABLE IF NOT EXISTS pedidos_clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_nombre TEXT NOT NULL,
    telefono TEXT,
    marca TEXT,
    modelo TEXT,
    version TEXT,
    anio_desde INTEGER,
    anio_hasta INTEGER,
    precio_maximo REAL,
    forma_pago TEXT,
    estado TEXT DEFAULT 'buscando',
    observaciones TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS precios_base (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marca TEXT NOT NULL,
    modelo TEXT NOT NULL,
    version TEXT NOT NULL,
    anio INTEGER NOT NULL,
    precio_referencia REAL NOT NULL,
    fuente TEXT DEFAULT 'InfoAuto',
    fecha_actualizacion TEXT DEFAULT (date('now'))
);

CREATE TABLE IF NOT EXISTS tomas_vehiculo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehiculo_id INTEGER,
    marca TEXT,
    modelo TEXT,
    version TEXT,
    anio INTEGER,
    evaluador TEXT,
    motor TEXT,
    caja TEXT,
    embrague TEXT,
    frenos TEXT,
    suspension TEXT,
    direccion TEXT,
    interior TEXT,
    tapizados TEXT,
    cubiertas TEXT,
    electricidad TEXT,
    aire_acondicionado TEXT,
    documentacion TEXT,
    observaciones TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id)
);

CREATE TABLE IF NOT EXISTS inspeccion_visual (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    toma_id INTEGER,
    vista TEXT NOT NULL,
    imagen_url TEXT,
    FOREIGN KEY (toma_id) REFERENCES tomas_vehiculo(id)
);

CREATE TABLE IF NOT EXISTS inspeccion_marcadores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspeccion_visual_id INTEGER NOT NULL,
    pos_x REAL,
    pos_y REAL,
    tipo TEXT,
    gravedad TEXT,
    descripcion TEXT,
    foto_url TEXT,
    FOREIGN KEY (inspeccion_visual_id) REFERENCES inspeccion_visual(id)
);

CREATE TABLE IF NOT EXISTS tasaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marca TEXT,
    modelo TEXT,
    version TEXT,
    anio INTEGER,
    valor_referencia REAL,
    estado_mecanico TEXT,
    estado_estetico TEXT,
    gastos_estimados REAL,
    precio_max_recomendado REAL,
    riesgo TEXT,
    margen_esperado REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS financiaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehiculo_id INTEGER,
    cliente_nombre TEXT NOT NULL,
    cliente_telefono TEXT,
    precio_venta REAL,
    anticipo REAL DEFAULT 0,
    monto_financiado REAL NOT NULL,
    tasa_interes_mensual REAL NOT NULL DEFAULT 0,
    metodo_interes TEXT NOT NULL DEFAULT 'frances',
    periodicidad TEXT NOT NULL DEFAULT 'mensual',
    plazo_meses INTEGER NOT NULL DEFAULT 0,
    cantidad_cuotas INTEGER NOT NULL,
    valor_cuota REAL NOT NULL,
    fecha_inicio TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'activo',
    observaciones TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id)
);

CREATE TABLE IF NOT EXISTS financiacion_cuotas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    financiacion_id INTEGER NOT NULL,
    numero INTEGER NOT NULL,
    fecha_vencimiento TEXT,
    monto REAL NOT NULL,
    monto_pagado REAL NOT NULL DEFAULT 0,
    fecha_pago TEXT,
    estado TEXT NOT NULL DEFAULT 'pendiente',
    FOREIGN KEY (financiacion_id) REFERENCES financiaciones(id)
);

CREATE TABLE IF NOT EXISTS red_publicaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agencia_nombre TEXT NOT NULL,
    tipo TEXT NOT NULL,
    marca TEXT,
    modelo TEXT,
    version TEXT,
    anio INTEGER,
    precio REAL,
    descripcion TEXT,
    contacto TEXT,
    estado TEXT DEFAULT 'activo',
    created_at TEXT DEFAULT (datetime('now'))
);
"""

# Datos de ejemplo para que la app se pueda probar de entrada.
# Mismos modelos que aparecen en el prototipo visual de referencia.
_SEED_PRECIOS = [
    # marca, modelo, version, anio, precio_referencia
    ("Toyota", "Hilux", "4x4 SRV", 2023, 46200000),
    ("Toyota", "Hilux", "4x4 SRV", 2022, 39800000),
    ("Toyota", "Hilux", "4x4 SRV", 2021, 32500000),
    ("Toyota", "Hilux", "4x4 SRV", 2020, 27900000),
    ("Toyota", "Hilux", "4x4 SRV", 2019, 24100000),
    ("Chevrolet", "Onix", "LTZ", 2023, 21500000),
    ("Chevrolet", "Onix", "LTZ", 2022, 18200000),
    ("Chevrolet", "Onix", "LTZ", 2021, 16400000),
    ("Chevrolet", "Onix", "LTZ", 2020, 14800000),
    ("Volkswagen", "Amarok", "V6 Highline", 2023, 41000000),
    ("Volkswagen", "Amarok", "V6 Highline", 2022, 34500000),
    ("Volkswagen", "Amarok", "V6 Highline", 2021, 31200000),
    ("Volkswagen", "Amarok", "V6 Highline", 2020, 28900000),
    ("Ford", "Focus", "SE", 2019, 14300000),
    ("Ford", "Focus", "SE", 2018, 12700000),
    ("Ford", "Focus", "SE", 2017, 11200000),
    ("Renault", "Duster", "Privilege", 2023, 24800000),
    ("Renault", "Duster", "Privilege", 2022, 21100000),
    ("Renault", "Duster", "Privilege", 2021, 18600000),
    ("Renault", "Duster", "Privilege", 2020, 16400000),
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _migrar_vehiculos(conn):
    """Agrega a `vehiculos` las columnas que necesita la sincronización con
    STOCK, sin tocar bases ya existentes (ALTER TABLE solo si falta la
    columna)."""
    columnas_actuales = {row[1] for row in conn.execute("PRAGMA table_info(vehiculos)")}
    nuevas_columnas = {
        "carpeta_stock": "TEXT",
        "ubicacion": "TEXT",
        "condiciones_pago": "TEXT",
        "estado_general": "TEXT",
    }
    for columna, tipo in nuevas_columnas.items():
        if columna not in columnas_actuales:
            conn.execute(f"ALTER TABLE vehiculos ADD COLUMN {columna} {tipo}")

    # Único índice: una carpeta de STOCK no puede mapear a más de un vehículo.
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_vehiculos_carpeta_stock "
        "ON vehiculos(carpeta_stock) WHERE carpeta_stock IS NOT NULL"
    )


def _migrar_pedidos(conn):
    """Agrega a `pedidos_clientes` los campos de financiación (efectivo /
    cuota) y los del vehículo que el cliente ofrece en permuta, sin tocar
    bases ya existentes."""
    columnas_actuales = {row[1] for row in conn.execute("PRAGMA table_info(pedidos_clientes)")}
    nuevas_columnas = {
        "efectivo_disponible": "REAL",
        "cuota_maxima": "REAL",
        "permuta_marca": "TEXT",
        "permuta_modelo": "TEXT",
        "permuta_version": "TEXT",
        "permuta_anio": "INTEGER",
        "permuta_km": "INTEGER",
        "permuta_combustible": "TEXT",
        "permuta_caja": "TEXT",
        "permuta_color": "TEXT",
        "permuta_observaciones": "TEXT",
    }
    for columna, tipo in nuevas_columnas.items():
        if columna not in columnas_actuales:
            conn.execute(f"ALTER TABLE pedidos_clientes ADD COLUMN {columna} {tipo}")


def _migrar_tomas_costos(conn):
    """Agrega a `tomas_vehiculo` un costo estimado de reparación por cada
    uno de los 12 puntos técnicos evaluados (motor, caja, tapizados, etc.),
    para poder sumarlos y sugerir los gastos de reparación en el paso de
    Tasación, sin tocar bases existentes."""
    columnas_actuales = {row[1] for row in conn.execute("PRAGMA table_info(tomas_vehiculo)")}
    puntos = [
        "motor", "caja", "embrague", "frenos", "suspension", "direccion", "interior",
        "tapizados", "cubiertas", "electricidad", "aire_acondicionado", "documentacion",
    ]
    for codigo in puntos:
        columna = f"costo_{codigo}"
        if columna not in columnas_actuales:
            conn.execute(f"ALTER TABLE tomas_vehiculo ADD COLUMN {columna} REAL")


def _migrar_tomas_comentarios(conn):
    """Agrega a `tomas_vehiculo` un comentario de texto libre por cada uno
    de los 12 puntos técnicos (en qué consiste la reparación, no solo
    cuánto cuesta), pedido en la charla del 14/09/2026. Mismos 12 códigos
    que _migrar_tomas_costos — si más adelante se amplía la lista de
    puntos, hay que sumar sus columnas costo_/comentario_ acá también."""
    columnas_actuales = {row[1] for row in conn.execute("PRAGMA table_info(tomas_vehiculo)")}
    puntos = [
        "motor", "caja", "embrague", "frenos", "suspension", "direccion", "interior",
        "tapizados", "cubiertas", "electricidad", "aire_acondicionado", "documentacion",
    ]
    for codigo in puntos:
        columna = f"comentario_{codigo}"
        if columna not in columnas_actuales:
            conn.execute(f"ALTER TABLE tomas_vehiculo ADD COLUMN {columna} TEXT")


def _migrar_inspeccion_marcadores(conn):
    """Agrega el costo estimado de reparación de cada daño marcado en la
    Inspección visual, para poder sumarlos y sugerir los gastos de
    reparación en el paso de Tasación."""
    columnas_actuales = {row[1] for row in conn.execute("PRAGMA table_info(inspeccion_marcadores)")}
    if "costo_reparacion" not in columnas_actuales:
        conn.execute("ALTER TABLE inspeccion_marcadores ADD COLUMN costo_reparacion REAL")


def _migrar_financiaciones(conn):
    """Agrega a `financiaciones` el método de interés (francés / interés
    simple), la periodicidad de cobro (mensual / semanal) y el plazo en
    meses usado para calcular la cuota, pedidos por Daniel el 14/09/2026
    para poder elegir por plan — sin tocar bases ya creadas con la versión
    anterior de la tabla (solo monto financiado mensual, francés)."""
    columnas_actuales = {row[1] for row in conn.execute("PRAGMA table_info(financiaciones)")}
    nuevas_columnas = {
        "metodo_interes": "TEXT NOT NULL DEFAULT 'frances'",
        "periodicidad": "TEXT NOT NULL DEFAULT 'mensual'",
        "plazo_meses": "INTEGER NOT NULL DEFAULT 0",
    }
    for columna, tipo in nuevas_columnas.items():
        if columna not in columnas_actuales:
            conn.execute(f"ALTER TABLE financiaciones ADD COLUMN {columna} {tipo}")
    # Planes creados antes de este cambio no tenían plazo_meses guardado —
    # lo completamos con cantidad_cuotas (mismo valor cuando eran mensuales).
    conn.execute("UPDATE financiaciones SET plazo_meses = cantidad_cuotas WHERE plazo_meses = 0")


def _migrar_tasaciones(conn):
    """Vincula `tasaciones` con la Toma de la que surgió (flujo unificado
    Toma → Fotos/Inspección visual → Tasación), sin tocar bases existentes."""
    columnas_actuales = {row[1] for row in conn.execute("PRAGMA table_info(tasaciones)")}
    if "toma_id" not in columnas_actuales:
        conn.execute("ALTER TABLE tasaciones ADD COLUMN toma_id INTEGER REFERENCES tomas_vehiculo(id)")


def _migrar_red_publicaciones(conn):
    """Agrega el kilometraje a `red_publicaciones` — para que el buscador
    combinado de Stock (ver buscador.py) pueda filtrar por Km también en
    las publicaciones de la Red de Agencieros, no solo en el stock propio.
    Pedido de Daniel 15/09/2026 (continuación 18)."""
    columnas_actuales = {row[1] for row in conn.execute("PRAGMA table_info(red_publicaciones)")}
    if "km" not in columnas_actuales:
        conn.execute("ALTER TABLE red_publicaciones ADD COLUMN km INTEGER")


def _migrar_tomas_checklist_ampliado(conn):
    """Amplía el checklist de la Toma técnica (Paso 1) de 12 a 44 puntos,
    15/09/2026, a partir de la planilla física de peritaje (SAKURA) que
    compartió Daniel: se agregan las columnas base (calificación),
    costo_<codigo> y comentario_<codigo> de cada punto nuevo, y se separa
    "cubiertas" en 5 puntos (uno por posición + auxilio). No se toca ni se
    borra ninguna columna existente — los 11 puntos que ya estaban (todos
    menos "cubiertas", que queda huérfana pero sin borrar por las tomas ya
    cargadas) siguen igual. También se agregan dos campos de texto libre
    nuevos: código de falla/testigo en tablero y último service realizado."""
    columnas_actuales = {row[1] for row in conn.execute("PRAGMA table_info(tomas_vehiculo)")}
    puntos_nuevos = [
        # Mecánica y carrocería (7 nuevos — el resto de este grupo ya existía)
        "distribucion", "tren_delantero", "linea_escape", "chapa", "pintura", "habitaculo", "bateria",
        # Cubiertas (reemplaza al punto único "cubiertas", que queda sin usar)
        "cubierta_del_der", "cubierta_del_izq", "cubierta_tras_der", "cubierta_tras_izq", "cubierta_auxilio",
        # Accesorios y equipamiento (todos nuevos)
        "luces", "levantavidrios", "espejos_electricos", "techo_corredizo", "limpia_parabrisas", "parabrisas",
        "luneta_termica", "cierre_electrico", "reg_altura_faros", "calefactor", "computadora_reloj",
        "control_satelital", "parlantes", "cinturones_seguridad", "criket", "llave_ruedas", "manuales",
        "duplicado_llave", "radio_cd_usb", "camara_retrovisora", "sensores_estacionamiento",
    ]
    for codigo in puntos_nuevos:
        if codigo not in columnas_actuales:
            conn.execute(f"ALTER TABLE tomas_vehiculo ADD COLUMN {codigo} TEXT")
        if f"costo_{codigo}" not in columnas_actuales:
            conn.execute(f"ALTER TABLE tomas_vehiculo ADD COLUMN costo_{codigo} REAL")
        if f"comentario_{codigo}" not in columnas_actuales:
            conn.execute(f"ALTER TABLE tomas_vehiculo ADD COLUMN comentario_{codigo} TEXT")
    if "codigo_falla" not in columnas_actuales:
        conn.execute("ALTER TABLE tomas_vehiculo ADD COLUMN codigo_falla TEXT")
    if "ultimo_service" not in columnas_actuales:
        conn.execute("ALTER TABLE tomas_vehiculo ADD COLUMN ultimo_service TEXT")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    _migrar_vehiculos(conn)
    _migrar_pedidos(conn)
    _migrar_tomas_costos(conn)
    _migrar_tomas_comentarios(conn)
    _migrar_tomas_checklist_ampliado(conn)
    _migrar_inspeccion_marcadores(conn)
    _migrar_tasaciones(conn)
    _migrar_financiaciones(conn)
    _migrar_red_publicaciones(conn)

    cur = conn.execute("SELECT COUNT(*) FROM precios_base")
    if cur.fetchone()[0] == 0:
        conn.executemany(
            """INSERT INTO precios_base (marca, modelo, version, anio, precio_referencia)
               VALUES (?, ?, ?, ?, ?)""",
            _SEED_PRECIOS,
        )

    cur = conn.execute("SELECT COUNT(*) FROM usuarios")
    if cur.fetchone()[0] == 0:
        conn.execute(
            """INSERT INTO usuarios (email, password_hash, nombre, agencia_nombre, is_admin)
               VALUES (?, ?, ?, ?, 1)""",
            ("admin@agencieros.com", generate_password_hash("admin1234"), "Admin", "Agencieros"),
        )

    cur = conn.execute("SELECT COUNT(*) FROM vehiculos")
    if cur.fetchone()[0] == 0:
        conn.executemany(
            """INSERT INTO vehiculos
               (marca, modelo, version, anio, km, combustible, caja, color, dominio, estado,
                valor_compra, gastos, valor_publicado, valor_vendido, fecha_ingreso, fecha_venta)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                ("Toyota", "Hilux", "4x4 SRV", 2021, 45000, "Diésel", "Automática", "Gris",
                 "AE123CD", "disponible", 27000000, 900000, 32500000, None, str(date.today()), None),
                ("Chevrolet", "Onix", "LTZ", 2020, 38000, "Nafta", "Manual", "Blanco",
                 "AF456GH", "disponible", 12500000, 400000, 14800000, None, str(date.today()), None),
                ("Volkswagen", "Amarok", "V6 Highline", 2020, 50000, "Diésel", "Automática", "Negro",
                 "AG789JK", "en_reparacion", 24000000, 1800000, 28900000, None, str(date.today()), None),
                ("Ford", "Focus", "SE", 2018, 60000, "Nafta", "Manual", "Rojo",
                 "AH012LM", "disponible", 10800000, 350000, 12700000, None, str(date.today()), None),
                ("Renault", "Duster", "Privilege", 2021, 42000, "Nafta", "Manual", "Gris",
                 "AJ345NP", "por_ingresar", 15200000, 0, 18600000, None, str(date.today()), None),
            ],
        )

    conn.commit()
    conn.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


# Fotos de muestra para habilitar la imagen principal en los listados de
# vehículos antes de tener fotos reales cargadas — se van alternando entre
# los vehículos que todavía no tienen ninguna foto propia (pedido de Daniel
# 15/09/2026). En cuanto un vehículo tiene su primera foto real (subida
# desde la ficha), esa pasa a ser la principal automáticamente y la de
# muestra deja de mostrarse para ese vehículo — no se guarda nada en
# `vehiculo_fotos`, es solo un reemplazo visual mientras no hay foto propia.
FOTOS_MUESTRA = ["img/muestra/auto1.jpg", "img/muestra/auto2.jpg"]


def foto_principal(vehiculo_id):
    """URL de la foto principal de un vehículo para mostrar en los listados:
    la primera foto real cargada (menor orden), o si todavía no tiene
    ninguna, una de las 2 fotos de muestra (alternando por id)."""
    from flask import url_for
    foto = query(
        "SELECT url FROM vehiculo_fotos WHERE vehiculo_id = ? ORDER BY orden, id LIMIT 1",
        (vehiculo_id,), one=True,
    )
    if foto:
        return foto["url"]
    return url_for("static", filename=FOTOS_MUESTRA[vehiculo_id % 2])


def obtener_catalogo():
    """Universo de Marca/Modelo/Versión ya usados en toda la app (precios_base
    + vehículos + pedidos + red + tomas + tasaciones), para que todos los
    formularios ofrezcan siempre las mismas opciones y no se generen
    duplicados por mayúsculas, tildes o espacios distintos.

    Devuelve {marca: {modelo: {version: [anios]}}} — el año de cada
    versión se suma para poder buscar/cargar empezando por el Año y que
    Marca/Modelo/Versión sugieran solo lo que corresponde a ese año (ver
    charla 13-14/09/2026). `anios` puede venir vacío cuando esa versión
    solo se vio en una fuente sin año propio (ej. un pedido de cliente sin
    permuta) — en ese caso no se filtra por año, para no ocultar datos por
    falta de ese dato puntual.

    Se recalcula en cada request (context_processor en app.py) así una
    marca/modelo/versión nueva cargada en cualquier módulo queda
    disponible para elegir en el resto al toque.
    """
    filas = query(
        """
        SELECT marca, modelo, version, anio FROM precios_base
        UNION ALL SELECT marca, modelo, version, anio FROM vehiculos
            WHERE marca IS NOT NULL AND TRIM(marca) != ''
        UNION ALL SELECT marca, modelo, version, NULL FROM pedidos_clientes
            WHERE marca IS NOT NULL AND TRIM(marca) != ''
        UNION ALL SELECT permuta_marca, permuta_modelo, permuta_version, permuta_anio FROM pedidos_clientes
            WHERE permuta_marca IS NOT NULL AND TRIM(permuta_marca) != ''
        UNION ALL SELECT marca, modelo, version, anio FROM red_publicaciones
            WHERE marca IS NOT NULL AND TRIM(marca) != ''
        UNION ALL SELECT marca, modelo, version, anio FROM tomas_vehiculo
            WHERE marca IS NOT NULL AND TRIM(marca) != ''
        UNION ALL SELECT marca, modelo, version, anio FROM tasaciones
            WHERE marca IS NOT NULL AND TRIM(marca) != ''
        """
    )
    catalogo = {}
    for fila in filas:
        marca, modelo, version, anio = fila["marca"], fila["modelo"], fila["version"], fila["anio"]
        if not marca:
            continue
        modelos = catalogo.setdefault(marca, {})
        if not modelo:
            continue
        versiones = modelos.setdefault(modelo, {})
        if not version:
            continue
        anios = versiones.setdefault(version, set())
        if anio is not None:
            anios.add(int(anio))

    for modelos in catalogo.values():
        for versiones in modelos.values():
            for version, anios in versiones.items():
                versiones[version] = sorted(anios)

    return catalogo
