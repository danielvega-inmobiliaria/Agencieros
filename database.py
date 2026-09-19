import os
import sqlite3
from datetime import date
from flask import g
from werkzeug.security import generate_password_hash

from storage import db_path

DB_PATH = db_path()

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
    tasa_interes_punitorio REAL NOT NULL DEFAULT 0,
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

CREATE TABLE IF NOT EXISTS garantes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    financiacion_id INTEGER NOT NULL,
    nombre TEXT NOT NULL,
    dni TEXT,
    telefono TEXT,
    domicilio TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (financiacion_id) REFERENCES financiaciones(id)
);

CREATE TABLE IF NOT EXISTS ventas (
    -- Venta directa desde Stock, SIN financiación (19/09/2026). Una fila
    -- por operación: nace como 'senado' cuando se recibe una seña, pasa a
    -- 'cerrada' al cerrar la venta, o a 'cancelada' si se cae. Una venta
    -- de contado puede nacer directo 'cerrada' (sin seña previa).
    -- efectivo_cobrado = TODO el efectivo que entró (seña INCLUIDA): la
    -- seña es solo la parte que llegó antes, nunca se suma aparte.
    -- Identidad: precio_venta = permuta_valor + efectivo_cobrado.
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agencia_id INTEGER,
    vehiculo_id INTEGER NOT NULL,
    estado TEXT NOT NULL DEFAULT 'senado',
    estado_previo TEXT,
    cliente_nombre TEXT,
    cliente_telefono TEXT,
    precio_venta REAL,
    sena REAL DEFAULT 0,
    fecha_sena TEXT,
    permuta_tasacion_id INTEGER,
    permuta_valor REAL,
    permuta_descripcion TEXT,
    efectivo_cobrado REAL,
    fecha_venta TEXT,
    observaciones TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id)
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

-- Admin (17/09/2026): datos de perfil de la agencia -- logo, nombre
-- comercial, dirección, teléfono y redes -- para usar en lo que mira el
-- cliente final (ficha comercial) y más adelante en cualquier otro lugar
-- de cara al público. Fila única (id fijo = 1), no hay multi-agencia
-- todavía. `telefono` va en formato listo para wa.me (solo dígitos, con
-- 549 adelante) -- se explica en el propio formulario de Admin.
CREATE TABLE IF NOT EXISTS agencia_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    nombre_agencia TEXT,
    logo_url TEXT,
    direccion TEXT,
    telefono TEXT,
    instagram TEXT,
    facebook TEXT,
    sitio_web TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Red de Agencieros multi-tenant (18/09/2026): cada agencia que se
-- registra es una cuenta real, con su propio login y su propia copia de
-- toda la app (Stock, Financiación, Tomas, etc. separados por
-- `agencia_id` en cada tabla de negocio -- ver las migraciones
-- `_migrar_multi_tenant_*` más abajo). Auth simple (registro + login +
-- validación por mail con código de 6 dígitos vía Resend) -- sin cobro
-- todavía, eso queda para cuando se definan los planes de suscripción
-- (pendiente 🔴 aparte).
CREATE TABLE IF NOT EXISTS agencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_agencia TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    telefono TEXT,
    email_verificado INTEGER DEFAULT 0,
    activo INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS verificacion_codigos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agencia_id INTEGER NOT NULL,
    codigo TEXT NOT NULL,
    expira_at TEXT NOT NULL,
    usado INTEGER DEFAULT 0,
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
        # Para un vehículo "Por ingresar": quién lo entrega (proveedor,
        # cliente, otra agencia, etc.) y la fecha en la que se estima que
        # va a ingresar físicamente — distinta de `fecha_ingreso`, que es la
        # fecha real en la que se cargó el vehículo (pedido de Daniel
        # 15/09/2026, continuación 24).
        "entrega_quien": "TEXT",
        "fecha_ingreso_estimada": "TEXT",
        # Si el vehículo es propio de la agencia o está en consignación (lo
        # entregó un tercero para vender, sin ser todavía de la agencia) —
        # cuando es consignación, se guarda además quién lo dejó (nombre y
        # teléfono) para poder ubicarlo (pedido de Daniel 15/09/2026,
        # continuación 25).
        "propiedad": "TEXT DEFAULT 'propio'",
        "consignante_nombre": "TEXT",
        "consignante_telefono": "TEXT",
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
    anterior de la tabla (solo monto financiado mensual, francés).

    17/09/2026: se suma `tasa_interes_punitorio` -- % que se acumula cada
    30 días de atraso sobre una cuota vencida (ej. 10% fijo cada 30 días,
    el criterio real que ya usa Daniel), para que la app pueda sugerir el
    monto a cobrar en vez de calcularlo a mano."""
    columnas_actuales = {row[1] for row in conn.execute("PRAGMA table_info(financiaciones)")}
    nuevas_columnas = {
        "metodo_interes": "TEXT NOT NULL DEFAULT 'frances'",
        "periodicidad": "TEXT NOT NULL DEFAULT 'mensual'",
        "plazo_meses": "INTEGER NOT NULL DEFAULT 0",
        "tasa_interes_punitorio": "REAL NOT NULL DEFAULT 0",
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


def _migrar_tomas_falla_service_si_no(conn):
    """"Código de falla / testigo en tablero" y "Último service realizado"
    pasaron de texto libre a Sí/No + comentario condicional (mismo criterio
    que los puntos del checklist: el comentario solo se abre si la
    respuesta es "Sí") — se agregan las 2 columnas de bandera; las columnas
    de texto (codigo_falla, ultimo_service) ya existían y se siguen
    usando para el comentario. Tomas cargadas antes de este cambio quedan
    con la bandera en NULL, sin perder el texto libre que ya tenían
    cargado (pedido de Daniel 15/09/2026, continuación 30)."""
    columnas_actuales = {row[1] for row in conn.execute("PRAGMA table_info(tomas_vehiculo)")}
    if "tiene_codigo_falla" not in columnas_actuales:
        conn.execute("ALTER TABLE tomas_vehiculo ADD COLUMN tiene_codigo_falla TEXT")
    if "tuvo_ultimo_service" not in columnas_actuales:
        conn.execute("ALTER TABLE tomas_vehiculo ADD COLUMN tuvo_ultimo_service TEXT")


def _limpiar_marketing_vehiculo(conn):
    """Elimina la tabla `marketing_vehiculo` (módulo Marketing, agregado y
    sacado el mismo 17/09/2026 por decisión de Daniel: primero probó el
    organizador de contenido, pero decidió dejar Marketing entero afuera de
    esta v1). Solo hace falta en bases que ya lo habían creado -- no está más
    en el SCHEMA, así que una base nueva nunca la tiene."""
    conn.execute("DROP TABLE IF EXISTS marketing_vehiculo")


def _limpiar_tomas_demo(conn):
    """Elimina las Tomas de ejemplo que quedaron de las pruebas iniciales de
    la app -- Chevrolet Onix, Ford Focus, Renault Duster, 2x Chevrolet
    CAPTIVA, Chevrolet AGILE y Chevrolet CAMARO (ids 1 a 7) -- identificadas
    por Daniel como datos de prueba después de terminar de ordenar su Stock
    real (pedido 17/09/2026). Solo toca esos ids puntuales, y solo si
    siguen sin vehiculo_id (por si alguno se llegó a vincular a mano a un
    auto real con el botón temporal de "Vincular a Stock") -- no borra
    ninguna Toma real ni vehículos de Stock, solo estos registros de Toma y
    tasación."""
    ids_demo = (1, 2, 3, 4, 5, 6, 7)
    placeholders = ",".join("?" for _ in ids_demo)
    filas = conn.execute(
        f"SELECT id FROM tomas_vehiculo WHERE id IN ({placeholders}) AND vehiculo_id IS NULL",
        ids_demo,
    ).fetchall()
    ids_a_borrar = [f[0] for f in filas]
    if not ids_a_borrar:
        return
    ph2 = ",".join("?" for _ in ids_a_borrar)
    conn.execute(
        f"""DELETE FROM inspeccion_marcadores WHERE inspeccion_visual_id IN (
                SELECT id FROM inspeccion_visual WHERE toma_id IN ({ph2})
            )""",
        ids_a_borrar,
    )
    conn.execute(f"DELETE FROM inspeccion_visual WHERE toma_id IN ({ph2})", ids_a_borrar)
    conn.execute(f"DELETE FROM tasaciones WHERE toma_id IN ({ph2})", ids_a_borrar)
    conn.execute(f"DELETE FROM tomas_vehiculo WHERE id IN ({ph2})", ids_a_borrar)


def _fusionar_duplicados_stock_manual(conn):
    """Corrige la primera corrida real de "Sincronizar desde STOCK"
    (17/09/2026): esa sincronización matchea carpetas de STOCK/ contra
    vehículos ya vinculados por `carpeta_stock`, pero el Fiat ARGO (id 7) y
    el Peugeot 408 (id 8) habían sido cargados a mano antes (por foto del
    título, con dominio real) y todavía no tenían `carpeta_stock` -- la
    sincronización no los reconoció y creó dos vehículos duplicados (ids 10
    y 11) en vez de vincularlos. `sync_stock.py` ya se corrigió para que
    esto no vuelva a pasar; esta función es solo la corrección puntual y
    única de esos dos duplicados ya creados en la base real de Daniel.

    Por cada par (manual, duplicado): pasa cualquier referencia que pudiera
    haber quedado apuntando al duplicado (fotos, tomas, financiaciones) al
    vehículo manual, completa en el manual los datos de STOCK/ que todavía
    tenga vacíos (sin pisar marca/modelo/versión/dominio ya cargados a
    mano), lo vincula a la carpeta de STOCK/, y borra el duplicado. Solo
    actúa si esos ids puntuales siguen existiendo tal cual -- no es un
    dedupe general, así que no toca nada más."""
    conn.row_factory = sqlite3.Row
    pares = (
        {"manual_id": 7, "duplicado_id": 10, "marca": "fiat", "modelo": "argo", "anio": 2018},
        {"manual_id": 8, "duplicado_id": 11, "marca": "peugeot", "modelo": "408", "anio": 2012},
    )
    for par in pares:
        manual = conn.execute(
            "SELECT * FROM vehiculos WHERE id = ? AND LOWER(marca) = ? AND LOWER(modelo) = ? AND anio = ?",
            (par["manual_id"], par["marca"], par["modelo"], par["anio"]),
        ).fetchone()
        duplicado = conn.execute(
            "SELECT * FROM vehiculos WHERE id = ? AND LOWER(marca) = ? AND LOWER(modelo) = ? AND anio = ?",
            (par["duplicado_id"], par["marca"], par["modelo"], par["anio"]),
        ).fetchone()
        if not manual or not duplicado or not duplicado["carpeta_stock"]:
            continue

        conn.execute("UPDATE vehiculo_fotos SET vehiculo_id = ? WHERE vehiculo_id = ?",
                     (manual["id"], duplicado["id"]))
        conn.execute("UPDATE tomas_vehiculo SET vehiculo_id = ? WHERE vehiculo_id = ?",
                     (manual["id"], duplicado["id"]))
        conn.execute("UPDATE financiaciones SET vehiculo_id = ? WHERE vehiculo_id = ?",
                     (manual["id"], duplicado["id"]))

        carpeta_stock = duplicado["carpeta_stock"]
        km = duplicado["km"]
        combustible = duplicado["combustible"]
        caja = duplicado["caja"]
        ubicacion = duplicado["ubicacion"]
        condiciones_pago = duplicado["condiciones_pago"]
        estado_general = duplicado["estado_general"]
        equipamiento = duplicado["equipamiento"]
        valor_publicado = duplicado["valor_publicado"]

        # Borrar el duplicado primero: `carpeta_stock` es UNIQUE, así que no
        # se puede asignar al manual mientras el duplicado todavía la tenga.
        conn.execute("DELETE FROM vehiculos WHERE id = ?", (duplicado["id"],))

        conn.execute(
            """UPDATE vehiculos SET
                 carpeta_stock = ?,
                 km = COALESCE(km, ?),
                 combustible = COALESCE(combustible, ?),
                 caja = COALESCE(caja, ?),
                 ubicacion = COALESCE(ubicacion, ?),
                 condiciones_pago = COALESCE(condiciones_pago, ?),
                 estado_general = COALESCE(estado_general, ?),
                 equipamiento = COALESCE(equipamiento, ?),
                 valor_publicado = CASE WHEN valor_publicado IS NULL OR valor_publicado = 0
                                         THEN ? ELSE valor_publicado END,
                 updated_at = datetime('now')
               WHERE id = ?""",
            (
                carpeta_stock, km, combustible, caja, ubicacion, condiciones_pago,
                estado_general, equipamiento, valor_publicado, manual["id"],
            ),
        )


def _cargar_financiacion_gol_historica(conn):
    """Carga el plan de financiación real del Volkswagen Gol Power 2004
    (id 12, sincronizado desde STOCK/) que Daniel ya había vendido y
    empezado a cobrar fuera de la app, con las cuotas que ya había cobrado
    (pedido 17/09/2026): vendido el 24/06/2026, cuota de $290.000/mes desde
    el 10/07/2026 (interés simple, 6% mensual sobre $2.000.000 a 12 cuotas,
    con anticipo de $3.500.000 sobre un precio de $5.500.000), con las
    cuotas de julio, agosto y septiembre ya cobradas al día 10 de cada mes.

    Corre una sola vez: si ya existe cualquier plan de financiación para
    este vehículo (cargado por esta migración o a mano desde la app), no
    hace nada -- así no se duplica si Daniel llega a cargarlo él mismo
    antes de que el servidor se reinicie."""
    conn.row_factory = sqlite3.Row
    vehiculo = conn.execute(
        "SELECT * FROM vehiculos WHERE id = 12 AND UPPER(marca) = 'VOLKSWAGEN' AND UPPER(modelo) = 'GOL'"
    ).fetchone()
    if not vehiculo:
        return
    ya_existe = conn.execute("SELECT 1 FROM financiaciones WHERE vehiculo_id = 12").fetchone()
    if ya_existe:
        return

    if vehiculo["estado"] != "vendido":
        conn.execute(
            """UPDATE vehiculos SET estado = 'vendido', valor_vendido = 5500000,
               fecha_venta = '2026-06-24', updated_at = datetime('now') WHERE id = 12"""
        )

    cur = conn.execute(
        """INSERT INTO financiaciones
           (vehiculo_id, cliente_nombre, cliente_telefono, precio_venta, anticipo,
            monto_financiado, tasa_interes_mensual, metodo_interes, periodicidad,
            plazo_meses, cantidad_cuotas, valor_cuota, fecha_inicio, observaciones)
           VALUES (12, 'Micaela Martinez', '3417077208', 5500000, 3500000,
                   2000000, 6, 'simple', 'mensual', 12, 12, 290000, '2026-07-10',
                   'Cargado retroactivamente el 17/09/2026: la venta y las primeras 3 cuotas ya se habían cobrado antes de usar este módulo.')"""
    )
    financiacion_id = cur.lastrowid

    fechas = [
        "2026-07-10", "2026-08-10", "2026-09-10", "2026-10-10", "2026-11-10", "2026-12-10",
        "2027-01-10", "2027-02-10", "2027-03-10", "2027-04-10", "2027-05-10", "2027-06-10",
    ]
    for numero, fecha in enumerate(fechas, start=1):
        pagada = numero <= 3
        conn.execute(
            """INSERT INTO financiacion_cuotas
               (financiacion_id, numero, fecha_vencimiento, monto, monto_pagado, fecha_pago, estado)
               VALUES (?,?,?,?,?,?,?)""",
            (
                financiacion_id, numero, fecha, 290000,
                290000 if pagada else 0, fecha if pagada else None,
                "pagada" if pagada else "pendiente",
            ),
        )


def _corregir_financiacion_cruze_lezcano(conn):
    """Corrige el plan de financiación de Laura Lezcano (Chevrolet CRUZE)
    que Daniel cargó dejando la fecha de la primera cuota en la sugerida
    por default (17/10/2026) en vez de la real (10/01/2026) -- ella viene
    pagando con un mes de atraso constante y un recargo fijo de 10% cada
    30 días, que Daniel calculaba a mano (pedido 17/09/2026).

    Recalcula el vencimiento de las 13 cuotas desde el 10/01/2026 (mensual,
    sin tocar números, montos ni pagos ya cargados) y carga la tasa de
    interés punitorio del plan en 10%. Corre una sola vez: si el plan ya
    no tiene la fecha de inicio equivocada, no hace nada -- así no pisa una
    corrección manual que Daniel haga desde la propia app."""
    conn.row_factory = sqlite3.Row
    fin = conn.execute(
        """SELECT f.* FROM financiaciones f
           JOIN vehiculos v ON v.id = f.vehiculo_id
           WHERE f.cliente_nombre = 'Laura Lezcano'
             AND UPPER(v.marca) = 'CHEVROLET' AND UPPER(v.modelo) = 'CRUZE'
             AND f.fecha_inicio = '2026-10-17'"""
    ).fetchone()
    if not fin:
        return

    cuotas = conn.execute(
        "SELECT * FROM financiacion_cuotas WHERE financiacion_id = ? ORDER BY numero", (fin["id"],)
    ).fetchall()
    base = date(2026, 1, 10)
    for c in cuotas:
        nueva_venc = _sumar_meses_simple(base, c["numero"] - 1)
        conn.execute(
            "UPDATE financiacion_cuotas SET fecha_vencimiento = ? WHERE id = ?",
            (str(nueva_venc), c["id"]),
        )
    conn.execute(
        "UPDATE financiaciones SET fecha_inicio = ?, tasa_interes_punitorio = 10 WHERE id = ?",
        (str(base), fin["id"]),
    )


def _sumar_meses_simple(fecha, meses):
    """Igual criterio que \`_sumar_meses\` de routes/financiacion.py (evita
    importar routes desde database.py): suma meses respetando fin de mes."""
    mes_total = fecha.month - 1 + meses
    anio = fecha.year + mes_total // 12
    mes = mes_total % 12 + 1
    import calendar as _calendar
    dia = min(fecha.day, _calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def _limpiar_stock_demo_muestra(conn):
    """Borra los vehículos de Stock que quedaron de la carga de ejemplo
    inicial -- Chevrolet Onix 2020, Volkswagen Amarok 2020, Ford Focus 2018
    y Renault Duster 2021 (ids 2 a 5) -- confirmados por Daniel como datos
    de muestra (pedido 17/09/2026). OJO: de la lista original de 6 quedan
    afuera a propósito el Toyota Hilux (id 1, hoy vendido con una
    financiación real cargada -- 'Ezequiel Petrini') y el LIFAN X50 (id 6,
    ya vinculado a una ficha real de Stock -- 'LIFAN_X50_2018_Roldan' -- por
    el sync); esos dos hay que confirmarlos aparte antes de tocarlos. Solo
    borra cada id si sigue matcheando exactamente marca/modelo/año Y no
    tiene fotos, financiación ni toma vinculada (por si alguno pasó a usarse
    de verdad después de la carga de ejemplo)."""
    candidatos = {
        2: ("Chevrolet", "Onix", 2020),
        3: ("Volkswagen", "Amarok", 2020),
        4: ("Ford", "Focus", 2018),
        5: ("Renault", "Duster", 2021),
    }
    for vehiculo_id, (marca, modelo, anio) in candidatos.items():
        fila = conn.execute(
            "SELECT id FROM vehiculos WHERE id = ? AND LOWER(marca) = LOWER(?) AND LOWER(modelo) = LOWER(?) AND anio = ?",
            (vehiculo_id, marca, modelo, anio),
        ).fetchone()
        if not fila:
            continue
        tiene_fotos = conn.execute(
            "SELECT 1 FROM vehiculo_fotos WHERE vehiculo_id = ?", (vehiculo_id,)
        ).fetchone()
        tiene_financiacion = conn.execute(
            "SELECT 1 FROM financiaciones WHERE vehiculo_id = ?", (vehiculo_id,)
        ).fetchone()
        tiene_toma = conn.execute(
            "SELECT 1 FROM tomas_vehiculo WHERE vehiculo_id = ?", (vehiculo_id,)
        ).fetchone()
        if tiene_fotos or tiene_financiacion or tiene_toma:
            continue
        conn.execute("DELETE FROM vehiculos WHERE id = ?", (vehiculo_id,))


def _limpiar_hilux_petrini_confirmado(conn):
    """Borra el Toyota Hilux (id 1, de la carga de ejemplo inicial) y su
    financiación asociada (cliente 'Ezequiel Petrini', cancelada, sin
    cobros reales -- ver _limpiar_stock_demo_muestra para el resto del
    lote). Daniel confirmó 17/09/2026 que este vehículo y ese crédito
    eran datos de prueba, a diferencia del LIFAN X50 (id 6) que sí quedó
    como dato real y no se toca. Verifica marca/modelo/año antes de
    borrar por si el id se reutilizó para un vehículo real después."""
    fila = conn.execute(
        "SELECT id FROM vehiculos WHERE id = 1 AND LOWER(marca) = 'toyota' AND LOWER(modelo) = 'hilux' AND anio = 2021"
    ).fetchone()
    if not fila:
        return
    planes = conn.execute(
        "SELECT id FROM financiaciones WHERE vehiculo_id = 1"
    ).fetchall()
    for plan in planes:
        conn.execute(
            "DELETE FROM financiacion_cuotas WHERE financiacion_id = ?", (plan["id"],)
        )
        conn.execute("DELETE FROM financiaciones WHERE id = ?", (plan["id"],))
    conn.execute("DELETE FROM vehiculo_fotos WHERE vehiculo_id = 1")
    conn.execute("DELETE FROM tomas_vehiculo WHERE vehiculo_id = 1")
    conn.execute("DELETE FROM vehiculos WHERE id = 1")


def _migrar_multi_tenant_agencias(conn):
    """Crea la agencia real de Daniel (id 1) a partir de su usuario admin
    actual, la primera vez que corre esta migración -- ver Red de
    Agencieros multi-tenant (18/09/2026). Reutiliza el mismo email y el
    mismo password_hash que ya tenía en `usuarios` (mismo login de
    siempre), toma el nombre comercial de `agencia_config` si ya lo había
    cargado en Admin (si no, cae a 'Tu agencia'), y la marca con el mail
    ya verificado (es el dueño de la cuenta, no hace falta que se mande un
    código a sí mismo). No toca `usuarios` -- esa tabla queda como estaba,
    sin usarse más para el login (ver routes/auth.py), por si hace falta
    mirar el historial."""
    if conn.execute("SELECT COUNT(*) FROM agencias").fetchone()[0] > 0:
        return
    admin = conn.execute(
        "SELECT * FROM usuarios WHERE email = 'admin@agencieros.com'"
    ).fetchone()
    if not admin:
        return
    config = conn.execute("SELECT nombre_agencia, telefono FROM agencia_config WHERE id = 1").fetchone()
    nombre_agencia = (config["nombre_agencia"] if config and config["nombre_agencia"] else None) or "Tu agencia"
    telefono = config["telefono"] if config else None
    conn.execute(
        """INSERT INTO agencias (id, nombre_agencia, email, password_hash, telefono, email_verificado, activo)
           VALUES (1, ?, ?, ?, ?, 1, 1)""",
        (nombre_agencia, admin["email"], admin["password_hash"], telefono),
    )
    # Alinea el autoincrement para que la próxima agencia que se registre
    # arranque en id 2, no choque con la 1 ya insertada a mano.
    conn.execute(
        "INSERT OR REPLACE INTO sqlite_sequence (name, seq) VALUES ('agencias', "
        "(SELECT MAX(id) FROM agencias))"
    )


def _migrar_agencia_config_multi_tenant(conn):
    """`agencia_config` era una fila única fija (id=1, CHECK) -- con
    multi-tenant cada agencia necesita la suya. SQLite no permite sacar un
    CHECK con ALTER TABLE, así que se recrea la tabla (mismo patrón que
    cualquier migración de esquema en SQLite: crear la nueva, copiar los
    datos, borrar la vieja) y se preserva la fila de Daniel como
    agencia_id 1."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(agencia_config)")]
    if "agencia_id" in cols:
        return
    fila_vieja = conn.execute("SELECT * FROM agencia_config WHERE id = 1").fetchone()
    conn.execute("ALTER TABLE agencia_config RENAME TO agencia_config_pre_multi_tenant")
    conn.execute(
        """CREATE TABLE agencia_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agencia_id INTEGER UNIQUE NOT NULL,
            nombre_agencia TEXT,
            logo_url TEXT,
            direccion TEXT,
            telefono TEXT,
            instagram TEXT,
            facebook TEXT,
            sitio_web TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )"""
    )
    if fila_vieja:
        conn.execute(
            """INSERT INTO agencia_config
               (agencia_id, nombre_agencia, logo_url, direccion, telefono, instagram, facebook, sitio_web, updated_at)
               VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fila_vieja["nombre_agencia"], fila_vieja["logo_url"], fila_vieja["direccion"],
                fila_vieja["telefono"], fila_vieja["instagram"], fila_vieja["facebook"],
                fila_vieja["sitio_web"], fila_vieja["updated_at"],
            ),
        )
    conn.execute("DROP TABLE agencia_config_pre_multi_tenant")


def _migrar_agencias_ultima_actividad(conn):
    """Última actividad por agencia (18/09/2026, Panel de Agencias): se pisa
    en cada request autenticado (ver app.py::_registrar_actividad) -- sirve
    para que el panel muestre qué tan viva está cada agencia de la Red, no
    solo sus datos de perfil. Arranca en NULL ("Nunca") hasta el primer
    request de cada agencia después de este cambio."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(agencias)")]
    if "ultima_actividad" not in cols:
        conn.execute("ALTER TABLE agencias ADD COLUMN ultima_actividad TEXT")


def _migrar_agencias_contacto_referencia(conn):
    """Contacto de referencia (18/09/2026, Panel de Agencias -- pedido de
    Daniel): nombre/cargo de la persona de referencia en cada agencia, para
    tener a quién llamar además del mail/teléfono general. Se carga en el
    formulario de inscripción (routes/auth.py::registro) y se muestra en la
    ficha de detalle del Panel de Agencias."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(agencias)")]
    if "contacto_referencia" not in cols:
        conn.execute("ALTER TABLE agencias ADD COLUMN contacto_referencia TEXT")


def _migrar_financiaciones_permuta(conn):
    """Agrega a `financiaciones` los datos de Permuta + Entrega Contado
    (19/09/2026, pedido de Daniel): al armar un credito con Otorgar/Guardar
    ahora se puede sumar un vehiculo que el cliente entrega como parte de
    pago, tomando como sugerencia el "Valor de toma" de una Tasacion ya
    hecha (permuta_tasacion_id + permuta_valor, este ultimo editable/
    redondeable a mano, o cargado directo si no hay tasacion) mas una
    descripcion libre (permuta_descripcion) para cuando no hay tasacion
    vinculada. `entrega_contado` es el efectivo que completa la operacion
    (precio de venta - permuta - monto financiado, sugerido pero se puede
    pisar a mano)."""
    columnas_actuales = {row[1] for row in conn.execute("PRAGMA table_info(financiaciones)")}
    nuevas_columnas = {
        "permuta_tasacion_id": "INTEGER REFERENCES tasaciones(id)",
        "permuta_valor": "REAL",
        "permuta_descripcion": "TEXT",
        "entrega_contado": "REAL",
    }
    for columna, tipo in nuevas_columnas.items():
        if columna not in columnas_actuales:
            conn.execute(f"ALTER TABLE financiaciones ADD COLUMN {columna} {tipo}")


def _migrar_agencia_config_ciudad_provincia(conn):
    """Ubicación estructurada (18/09/2026, Panel de Agencias): Ciudad y
    Provincia como columnas separadas de `agencia_config`, además de la
    Dirección de texto libre que ya existía -- pedido de Daniel para poder
    ver/agrupar las agencias de la Red por zona en el panel nuevo
    (routes/plataforma.py), algo que con Dirección como texto libre
    ("Roldán, Santa Fe" todo junto) no se podía hacer de forma confiable."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(agencia_config)")]
    if "ciudad" not in cols:
        conn.execute("ALTER TABLE agencia_config ADD COLUMN ciudad TEXT")
    if "provincia" not in cols:
        conn.execute("ALTER TABLE agencia_config ADD COLUMN provincia TEXT")


def _migrar_multi_tenant_columnas(conn):
    """Agrega `agencia_id` a las tablas de negocio "raíz" (las que se
    consultan directo por agencia en las rutas) y deja todo lo que ya
    existía marcado como de la agencia 1 (Daniel/Italia Automotores) --
    así ningún dato viejo queda huérfano. Las tablas hijas (vehiculo_fotos,
    financiacion_cuotas, inspeccion_visual, inspeccion_marcadores) no
    llevan su propia columna: se llega a ellas siempre a través del id del
    padre (vehiculo_id/financiacion_id/toma_id), que ya queda protegido
    apenas se valide que el padre es de la agencia logueada -- por eso no
    hace falta duplicar la columna ahí.

    IMPORTANTE (ver Pendientes en PROYECTO.md): agregar la columna acá NO
    alcanza por sí solo para que los datos queden separados -- cada ruta
    tiene que filtrar por `agencia_id = session['agencia_id']` a mano.
    Mientras eso no esté hecho para un módulo, `app.py` lo bloquea para
    cualquier agencia que no sea la 1, así no hay forma de que una agencia
    nueva vea datos de otra por un WHERE que todavía falta agregar."""
    tablas = [
        "vehiculos", "pedidos_clientes", "tomas_vehiculo",
        "tasaciones", "financiaciones", "red_publicaciones",
    ]
    for tabla in tablas:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tabla})")]
        if "agencia_id" not in cols:
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN agencia_id INTEGER")
        conn.execute(f"UPDATE {tabla} SET agencia_id = 1 WHERE agencia_id IS NULL")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    _migrar_vehiculos(conn)
    _migrar_pedidos(conn)
    _migrar_tomas_costos(conn)
    _migrar_tomas_comentarios(conn)
    _migrar_tomas_checklist_ampliado(conn)
    _migrar_tomas_falla_service_si_no(conn)
    _migrar_inspeccion_marcadores(conn)
    _migrar_tasaciones(conn)
    _migrar_financiaciones(conn)
    _migrar_red_publicaciones(conn)
    _limpiar_marketing_vehiculo(conn)
    _limpiar_tomas_demo(conn)
    _fusionar_duplicados_stock_manual(conn)
    _cargar_financiacion_gol_historica(conn)
    _corregir_financiacion_cruze_lezcano(conn)
    _limpiar_stock_demo_muestra(conn)
    _limpiar_hilux_petrini_confirmado(conn)
    _migrar_multi_tenant_agencias(conn)
    _migrar_agencia_config_multi_tenant(conn)
    _migrar_agencia_config_ciudad_provincia(conn)
    _migrar_agencias_ultima_actividad(conn)
    _migrar_agencias_contacto_referencia(conn)
    _migrar_financiaciones_permuta(conn)
    _migrar_multi_tenant_columnas(conn)

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


# Valores por default cuando todavía nadie completó el Admin -- "nunca
# inventes": todos en blanco/None, la ficha comercial y donde se use esto
# tienen que arreglárselas para no mostrar nada en vez de un dato trucho.
_CONFIG_AGENCIA_DEFAULT = {
    "nombre_agencia": None,
    "logo_url": None,
    "direccion": None,
    "ciudad": None,
    "provincia": None,
    "telefono": None,
    "instagram": None,
    "facebook": None,
    "sitio_web": None,
}


def obtener_config_agencia(agencia_id=1):
    """Datos de perfil de la agencia cargados en Admin (logo, nombre,
    dirección, teléfono, redes) -- una fila por agencia desde el
    multi-tenant de Red de Agencieros (18/09/2026, ver `agencia_id` en
    `agencia_config`). Default `agencia_id=1` para no romper los llamados
    viejos (ej. la ficha comercial pública de Stock, que por ahora sigue
    siendo solo de la agencia 1). Si esa agencia todavía no cargó nada,
    devuelve el default en blanco en vez de None, para no tener que estar
    chequeando en cada template si `config` existe."""
    fila = query("SELECT * FROM agencia_config WHERE agencia_id = ?", (agencia_id,), one=True)
    if fila is None:
        return dict(_CONFIG_AGENCIA_DEFAULT)
    return dict(fila)


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
