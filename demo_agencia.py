"""Agencia DEMO de AGENCIEROS (06/10/2026).

Una agencia ficticia ("Autos del Sur (Demo)") con todo cargado de ejemplo --
Stock, Pedidos, Toma y tasación, Financiación, ventas, Matches y Red -- para
mandarle a un agenciero que quiera ver cómo funciona la app. Entra con el
botón "Probar demo" (auth.demo), sin mail ni contraseña.

- `agencias.es_demo = 1`  -> la agencia demo.
- `agencias.es_demo = 2`  -> agencias ficticias de la Red demo (no se pueden
  loguear: solo "publican" en la Red de la demo).
- La Red de la demo está AISLADA: la demo solo ve publicaciones de agencias
  es_demo > 0 y las agencias reales no ven nada de la demo (utils/demo.py).
- Se reinicia sola la primera vez que alguien entra cada día (y a mano desde
  el Panel de Agencias): borra todo lo de la agencia demo y lo vuelve a cargar.
- Las fotos son ilustraciones generadas (static/demo/*.jpg, ver
  `generar_fotos`), nunca fotos de terceros.

Uso por consola (opcional):
    python demo_agencia.py            -> reinicia la demo
    python demo_agencia.py fotos      -> regenera static/demo/*.jpg
"""
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash

EMAIL_DEMO = "demo@agencieros.net.ar"
NOMBRE_DEMO = "Autos del Sur (Demo)"
_BASE = os.path.dirname(os.path.abspath(__file__))
CARPETA_FOTOS = os.path.join(_BASE, "static", "demo")

# --------------------------------------------------------------------------
# Datos de ejemplo
# --------------------------------------------------------------------------
# (clave, marca, modelo, version, año, km, combustible, caja, color, tipo_carroceria,
#  estado, compra, gastos, publicado, sucursal(0 central / 1 norte), en_red, dominio)
VEHICULOS = [
    ("etios", "Toyota", "Etios", "1.5 XLS 5P", 2018, 68000, "Nafta", "Manual", "Blanco", "hatchback",
     "disponible", 11000000, 250000, 14500000, 0, True, "AB123CD"),
    ("gol", "Volkswagen", "Gol Trend", "1.6 Highline 5P", 2017, 82000, "Nafta", "Manual", "Gris", "hatchback",
     "disponible", 8200000, 180000, 10900000, 0, False, "AA456BC"),
    ("cruze", "Chevrolet", "Cruze", "1.4T LT 4P", 2018, 74000, "Nafta", "Manual", "Negro", "sedan",
     "disponible", 15000000, 300000, 18900000, 0, True, "AC789DE"),
    ("ranger", "Ford", "Ranger", "3.2 XLT 4x4 CD", 2017, 120000, "Diesel", "Manual", "Blanco", "pickup",
     "disponible", 28000000, 600000, 34500000, 0, True, "AB234FG"),
    ("duster", "Renault", "Duster", "2.0 Dynamique", 2019, 59000, "Nafta", "Manual", "Rojo", "suv",
     "disponible", 17500000, 350000, 21900000, 1, False, "AD567HI"),
    ("cronos", "Fiat", "Cronos", "1.3 Drive 4P", 2020, 45000, "Nafta", "Manual", "Gris", "sedan",
     "disponible", 14800000, 200000, 18200000, 1, True, "AE890JK"),
    ("corolla", "Toyota", "Corolla", "1.8 XEi CVT", 2017, 91000, "Nafta", "Automática", "Gris oscuro", "sedan",
     "disponible", 16500000, 400000, 20500000, 0, True, "AB345LM"),
    ("kangoo", "Renault", "Kangoo", "1.6 Express Confort", 2017, 98000, "Nafta/GNC", "Manual", "Blanco", "furgon_kangoo",
     "disponible", 9000000, 150000, 12500000, 1, False, "AA678NO"),
    ("208", "Peugeot", "208", "1.6 Allure 5P", 2019, 51000, "Nafta", "Manual", "Azul", "hatchback",
     "por_ingresar", 12500000, 0, 15800000, 0, False, "AD901PQ"),
    ("hilux", "Toyota", "Hilux", "2.8 SRV 4x4 CD", 2016, 165000, "Diesel", "Manual", "Plata", "pickup",
     "en_reparacion", 31000000, 900000, 37500000, 0, False, "AA012RS"),
    ("vento", "Volkswagen", "Vento", "2.0 TSI Luxury", 2015, 104000, "Nafta", "Manual", "Negro", "sedan",
     "senado", 14000000, 280000, 17500000, 0, False, "AB567TU"),
    ("onix", "Chevrolet", "Onix", "1.4 LTZ 5P", 2018, 63000, "Nafta", "Manual", "Blanco", "hatchback",
     "senado", 10200000, 220000, 13900000, 1, False, "AC123VW"),
    ("hrv", "Honda", "HR-V", "1.8 EXL CVT", 2018, 70000, "Nafta", "Automática", "Gris", "suv",
     "vendido", 19000000, 350000, 23500000, 0, False, "AB456XY"),
    ("frontier", "Nissan", "Frontier", "2.5 XE 4x4 CD", 2015, 138000, "Diesel", "Manual", "Plata", "pickup",
     "vendido", 20000000, 500000, 26000000, 0, False, "AA789ZA"),
]

# Colores de la ilustración (RGB) por nombre de color.
COLORES = {
    "Blanco": (240, 240, 240), "Gris": (160, 170, 185), "Negro": (70, 78, 95), "Rojo": (225, 80, 80),
    "Azul": (80, 130, 225), "Plata": (190, 198, 210), "Gris oscuro": (110, 120, 138),
}

PEDIDOS = [
    # (cliente, tel, marca, modelo, desde, hasta, precio_max, forma_pago, efectivo, cuota_max, permuta(dict|None), obs, estado)
    ("Carlos Méndez", "5493415550101", "Toyota", "Etios", 2018, 2019, 15000000, "contado", None, None, None,
     "Quiere hatchback económico, paga contado.", "buscando"),
    ("Lucía Ferreyra", "5493415550102", "Chevrolet", "Cruze", 2017, 2020, 19500000, "cuotas", 6000000, 450000, None,
     "Entrega 6 millones y el resto en cuotas.", "buscando"),
    ("Roberto Giménez", "5493415550103", "Ford", "Ranger", 2017, 2019, 35000000, "permuta", 8000000, None,
     {"marca": "Volkswagen", "modelo": "Gol", "version": "1.6 Power", "anio": 2012, "km": 140000,
      "combustible": "Nafta", "caja": "Manual", "color": "Gris", "obs": "Buen estado general."},
     "Entrega su Gol 2012 más efectivo.", "buscando"),
    ("Sofía Paredes", "5493415550104", "Renault", "Sandero", 2018, 2021, 14000000, "contado", None, None, None,
     "No hay en stock: se cruza con la Red.", "buscando"),
    ("Martín Acosta", "5493415550105", "Honda", "Civic", 2016, 2019, 22000000, "contado", None, None, None,
     "Busca sedán deportivo.", "buscando"),
    ("Daniela Ruiz", "5493415550106", "Fiat", "Cronos", 2019, 2021, 18500000, "contado", None, None, None,
     "Ya compró (pedido resuelto).", "resuelto"),
]

# Agencias ficticias de la Red demo: (nombre, tel contacto)
RED_AGENCIAS = [
    ("Rosario Motors", "5493415550201"), ("Autos Cuyo", "5492615550202"),
    ("Premium Cars Córdoba", "5493515550203"), ("Del Litoral Automotores", "5493425550204"),
]
# (agencia idx, tipo, marca, modelo, version, anio, km, precio, descripcion)
RED_PUBLICACIONES = [
    (0, "ofrezco", "Renault", "Sandero", "1.6 Stepway Intens", 2019, 55000, 13200000, "Excelente estado, único dueño."),
    (1, "ofrezco", "Honda", "Civic", "1.8 EXL", 2017, 87000, 21500000, "Service oficial al día."),
    (2, "ofrezco", "Toyota", "SW4", "2.8 SRX 4x4 7A", 2018, 98000, 42000000, "Full, cuero, 7 asientos."),
    (3, "ofrezco", "Volkswagen", "Amarok", "V6 Highline 4x4 CD", 2019, 76000, 44500000, "Muy buen estado."),
    (0, "ofrezco", "Ford", "Fiesta Kinetic", "1.6 SE", 2016, 92000, 9800000, "Recién ingresado."),
    (3, "busco", "Toyota", "Etios", "", 2017, None, 14500000, "Busco para cliente que paga contado."),
    (2, "busco", "Ford", "Ranger", "", 2016, None, 33000000, "Busco 4x4 doble cabina, diésel."),
    (1, "busco", "Chevrolet", "Onix", "", 2018, None, 13500000, "Cliente con efectivo."),
]


# --------------------------------------------------------------------------
# Fotos ilustrativas
# --------------------------------------------------------------------------
def generar_fotos(forzar=False):
    """Genera static/demo/<clave>.jpg: la silueta de la carrocería (las mismas
    ilustraciones que usa la Inspección visual) pintada del color del auto,
    sobre un fondo de la app, con marca/modelo. Son ilustraciones, no fotos."""
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    os.makedirs(CARPETA_FOTOS, exist_ok=True)

    def fuente(tam, negrita=False):
        for ruta in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrita else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                     "C:/Windows/Fonts/arialbd.ttf" if negrita else "C:/Windows/Fonts/arial.ttf"):
            try:
                return ImageFont.truetype(ruta, tam)
            except OSError:
                continue
        return ImageFont.load_default()

    for (clave, marca, modelo, version, anio, *_r) in VEHICULOS:
        destino = os.path.join(CARPETA_FOTOS, f"{clave}.jpg")
        if os.path.exists(destino) and not forzar:
            continue
        v = next(x for x in VEHICULOS if x[0] == clave)
        tipo, color = v[9], COLORES.get(v[8], (200, 200, 200))
        silueta = os.path.join(_BASE, "static", "img", "carrocerias", tipo, "lateral_der.png")
        W, H = 800, 600
        lienzo = Image.new("RGB", (W, H))
        d = ImageDraw.Draw(lienzo)
        for y in range(H):  # degradé vertical
            t = y / H
            d.line([(0, y), (W, y)], fill=(int(19 + 12 * t), int(30 + 14 * t), int(46 + 20 * t)))
        if os.path.exists(silueta):
            arte = Image.open(silueta).convert("L")
            mascara = ImageOps.invert(arte)  # líneas negras -> opacas
            ancho = 700
            alto = int(arte.height * ancho / arte.width)
            mascara = mascara.resize((ancho, alto), Image.LANCZOS)
            capa = Image.new("RGB", (ancho, alto), color)
            lienzo.paste(capa, ((W - ancho) // 2, 170), mascara)
        d.text((40, 40), f"{marca} {modelo}", font=fuente(44, True), fill=(238, 242, 247))
        d.text((40, 100), f"{version} · {anio}", font=fuente(26), fill=(154, 167, 187))
        d.text((40, H - 50), "Imagen ilustrativa de la demo", font=fuente(18), fill=(110, 124, 146))
        lienzo.save(destino, "JPEG", quality=84)


# --------------------------------------------------------------------------
# Reinicio / carga
# --------------------------------------------------------------------------
def _hoy_ar():
    """Fecha de hoy en Argentina (UTC-3)."""
    return (datetime.utcnow() - timedelta(hours=3)).date()


def _meses(fecha, n):
    mes = fecha.month - 1 + n
    anio = fecha.year + mes // 12
    mes = mes % 12 + 1
    dia = min(fecha.day, 28)
    return date(anio, mes, dia)


def _asegurar_agencia(conn, es_demo, nombre, email, telefono=None, activo=1):
    fila = conn.execute("SELECT id FROM agencias WHERE lower(email) = lower(?)", (email,)).fetchone()
    if fila:
        conn.execute("UPDATE agencias SET es_demo = ?, nombre_agencia = ?, activo = ?, email_verificado = 1, plan = 'libre' WHERE id = ?",
                     (es_demo, nombre, activo, fila[0]))
        return fila[0]
    cur = conn.execute(
        """INSERT INTO agencias (nombre_agencia, email, password_hash, telefono, email_verificado, activo, plan, es_demo)
           VALUES (?,?,?,?,1,?, 'libre', ?)""",
        (nombre, email, generate_password_hash(os.urandom(16).hex()), telefono, activo, es_demo),
    )
    return cur.lastrowid


def _borrar_datos(conn, agencia_id):
    q = "?"
    sub_v = "SELECT id FROM vehiculos WHERE agencia_id = ?"
    sub_t = "SELECT id FROM tomas_vehiculo WHERE agencia_id = ?"
    sub_f = "SELECT id FROM financiaciones WHERE agencia_id = ?"
    conn.execute(f"DELETE FROM vehiculo_fotos WHERE vehiculo_id IN ({sub_v})", (agencia_id,))
    conn.execute(f"DELETE FROM inspeccion_marcadores WHERE inspeccion_visual_id IN "
                 f"(SELECT id FROM inspeccion_visual WHERE toma_id IN ({sub_t}))", (agencia_id,))
    conn.execute(f"DELETE FROM inspeccion_visual WHERE toma_id IN ({sub_t})", (agencia_id,))
    conn.execute(f"DELETE FROM financiacion_cuotas WHERE financiacion_id IN ({sub_f})", (agencia_id,))
    conn.execute(f"DELETE FROM garantes WHERE financiacion_id IN ({sub_f})", (agencia_id,))
    for tabla in ("tasaciones", "tomas_vehiculo", "financiaciones", "ventas", "planes_oferta", "red_publicaciones",
                  "pedidos_clientes", "vehiculos", "consultas_precios", "mensajes_admin", "sucursales", "agencia_config"):
        conn.execute(f"DELETE FROM {tabla} WHERE agencia_id = {q}", (agencia_id,))


def reiniciar_demo(db_path=None):
    """Borra todo lo de la agencia demo y la Red ficticia y lo vuelve a cargar.
    Devuelve el id de la agencia demo."""
    if db_path is None:
        from database import DB_PATH as db_path
    generar_fotos()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        demo_id = _asegurar_agencia(conn, 1, NOMBRE_DEMO, EMAIL_DEMO, "5493410000000")
        red_ids = []
        for i, (nombre, tel) in enumerate(RED_AGENCIAS, start=1):
            # activo = 0: no se pueden loguear (solo aparecen en la Red demo).
            red_ids.append(_asegurar_agencia(conn, 2, nombre, f"red{i}.demo@agencieros.net.ar", tel, activo=0))
        _borrar_datos(conn, demo_id)
        for rid in red_ids:
            conn.execute("DELETE FROM red_publicaciones WHERE agencia_id = ?", (rid,))
        # Usuario dueño (el login normal no sirve: la clave es aleatoria).
        if not conn.execute("SELECT 1 FROM agencia_usuarios WHERE agencia_id = ?", (demo_id,)).fetchone():
            conn.execute(
                """INSERT INTO agencia_usuarios (agencia_id, nombre, email, password_hash, rol)
                   VALUES (?, 'Demo Agencieros', ?, ?, 'dueno')""",
                (demo_id, EMAIL_DEMO, generate_password_hash(os.urandom(16).hex())),
            )
        _cargar(conn, demo_id, red_ids)
        conn.execute("UPDATE agencias SET demo_reset_at = ? WHERE id = ?", (str(_hoy_ar()), demo_id))
        conn.commit()
        return demo_id
    finally:
        conn.close()


def _cargar(conn, demo_id, red_ids):
    from routes.tomas import PUNTOS

    hoy = _hoy_ar()
    iso = lambda d: str(d)

    # Perfil de la agencia + sucursales
    conn.execute(
        """INSERT INTO agencia_config (agencia_id, nombre_agencia, direccion, telefono, instagram, ciudad, provincia,
                                       nombre_contacto, margen_objetivo_pct)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (demo_id, NOMBRE_DEMO, "Av. Pellegrini 1234", "5493410000000", "@autosdelsur.demo", "Rosario",
         "Santa Fe", "Equipo Demo", 15),
    )
    suc_ids = []
    for nombre, direccion in (("Casa Central", "Av. Pellegrini 1234"), ("Sucursal Norte", "Bv. Rondeau 2450")):
        suc_ids.append(conn.execute(
            "INSERT INTO sucursales (agencia_id, nombre, direccion, ciudad, telefono) VALUES (?,?,?,?,?)",
            (demo_id, nombre, direccion, "Rosario", "5493410000000"),
        ).lastrowid)

    # Stock
    vid = {}
    for (clave, marca, modelo, version, anio, km, comb, caja, color, carroceria, estado, compra, gastos, pub,
         suc, en_red, dominio) in VEHICULOS:
        dias = {"etios": 21, "gol": 40, "cruze": 15, "ranger": 33, "duster": 9, "cronos": 12, "corolla": 6, "kangoo": 52,
                "208": 0, "hilux": 25, "vento": 30, "onix": 18, "hrv": 45, "frontier": 80}[clave]
        ingreso = hoy - timedelta(days=dias)
        vendido = estado == "vendido"
        valor_vendido = {"hrv": 23000000, "frontier": 25500000}.get(clave)
        fecha_venta = iso(hoy - timedelta(days={"hrv": 12, "frontier": 65}[clave])) if vendido else None
        cur = conn.execute(
            """INSERT INTO vehiculos (marca, modelo, version, anio, km, combustible, caja, color, dominio, estado,
                   equipamiento, observaciones, documentacion, valor_compra, gastos, valor_publicado, valor_vendido,
                   fecha_ingreso, fecha_venta, tipo_carroceria, agencia_id, sucursal_id, propiedad, fecha_ingreso_estimada)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'propio', ?)""",
            (marca, modelo, version, anio, km, comb, caja, color, dominio, estado,
             "Aire acondicionado, dirección asistida, levantacristales eléctricos, cierre centralizado, airbags, ABS.",
             "Unidad de ejemplo de la demo.", "Título y cédula verde al día. 08 firmado.",
             compra, gastos, pub, valor_vendido, iso(ingreso), fecha_venta, carroceria, demo_id, suc_ids[suc],
             iso(hoy + timedelta(days=5)) if estado == "por_ingresar" else None),
        )
        vid[clave] = cur.lastrowid
        conn.execute("INSERT INTO vehiculo_fotos (vehiculo_id, url, orden) VALUES (?,?,0)",
                     (cur.lastrowid, f"/static/demo/{clave}.jpg"))

    # Pedidos
    for (cli, tel, marca, modelo, desde, hasta, pmax, forma, efectivo, cuota, permuta, obs, estado) in PEDIDOS:
        p = permuta or {}
        conn.execute(
            """INSERT INTO pedidos_clientes (agencia_id, cliente_nombre, telefono, marca, modelo, anio_desde, anio_hasta,
                   precio_maximo, forma_pago, estado, observaciones, efectivo_disponible, cuota_maxima,
                   permuta_marca, permuta_modelo, permuta_version, permuta_anio, permuta_km, permuta_combustible,
                   permuta_caja, permuta_color, permuta_observaciones)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (demo_id, cli, tel, marca, modelo, desde, hasta, pmax, forma, estado, obs, efectivo, cuota,
             p.get("marca"), p.get("modelo"), p.get("version"), p.get("anio"), p.get("km"),
             p.get("combustible"), p.get("caja"), p.get("color"), p.get("obs")),
        )

    # Toma y tasación (3 casos)
    def alta_toma(vehiculo_clave, marca, modelo, version, anio, carroceria, puntos_mal, obs, estado_mec, estado_est,
                  valor_ref, gastos, max_rec, margen, hace_dias, danios=None):
        base = {c: "Bueno" for c, _ in PUNTOS}
        for c in ("control_satelital", "techo_corredizo", "sensores_estacionamiento", "camara_retrovisora",
                  "reg_altura_faros", "calefactor"):
            base[c] = "No posee"
        cols = ["vehiculo_id", "marca", "modelo", "version", "anio", "evaluador", "tipo_carroceria",
                "tiene_codigo_falla", "tuvo_ultimo_service", "observaciones", "agencia_id", "created_at"]
        vals = [vid.get(vehiculo_clave), marca, modelo, version, anio, "Demo Agencieros", carroceria,
                "No", "Si", obs, demo_id, f"{hoy - timedelta(days=hace_dias)} 11:30:00"]
        for c, _ in PUNTOS:
            cols.append(c)
            vals.append(puntos_mal.get(c, (base[c],))[0])
        for c, (cal, costo, comentario) in ((k, v) for k, v in puntos_mal.items()):
            cols += [f"costo_{c}", f"comentario_{c}"]
            vals += [costo, comentario]
        cur = conn.execute(f"INSERT INTO tomas_vehiculo ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)
        toma_id = cur.lastrowid
        conn.execute(
            """INSERT INTO tasaciones (toma_id, marca, modelo, version, anio, valor_referencia, estado_mecanico,
                   estado_estetico, gastos_estimados, precio_max_recomendado, riesgo, margen_esperado,
                   margen_objetivo_pct, agencia_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (toma_id, marca, modelo, version, anio, valor_ref, estado_mec, estado_est, gastos, max_rec,
             "Bajo" if not puntos_mal else "Medio", margen, 15, demo_id, f"{hoy - timedelta(days=hace_dias)} 12:10:00"),
        )
        for vista, marcadores in (danios or {}).items():
            vis = conn.execute("INSERT INTO inspeccion_visual (toma_id, vista) VALUES (?,?)", (toma_id, vista)).lastrowid
            for (x, y, tipo, grav, desc, costo) in marcadores:
                conn.execute(
                    """INSERT INTO inspeccion_marcadores (inspeccion_visual_id, pos_x, pos_y, tipo, gravedad, descripcion, costo_reparacion)
                       VALUES (?,?,?,?,?,?,?)""", (vis, x, y, tipo, grav, desc, costo))
        return toma_id

    alta_toma("corolla", "Toyota", "Corolla", "1.8 XEi CVT", 2017, "sedan",
              {"cubierta_del_izq": ("Regular", 90000, "Desgaste parejo, cambiar en 5.000 km"),
               "pintura": ("Regular", 120000, "Retoque en paragolpes trasero")},
              "Muy buen estado general. Service oficial al día.", "Bueno", "Bueno", 20500000, 210000, 17400000, 2890000, 6,
              danios={"lateral_der": [(32.0, 55.0, "rayon", "leve", "Rayón en puerta trasera", 60000)],
                      "trasera": [(48.0, 70.0, "paragolpes", "moderado", "Paragolpes marcado", 120000)]})
    alta_toma("hilux", "Toyota", "Hilux", "2.8 SRV 4x4 CD", 2016, "pickup",
              {"embrague": ("Malo", 480000, "Patina en segunda y tercera"),
               "frenos": ("Regular", 150000, "Pastillas al límite"),
               "suspension": ("Regular", 220000, "Bujes delanteros"),
               "tapizados": ("Regular", 90000, "Limpieza profunda")},
              "En reparación: embrague, frenos y suspensión.", "Regular", "Bueno", 37500000, 940000, 31000000, 5560000, 25)
    alta_toma(None, "Volkswagen", "Gol", "1.6 Power 3P", 2012, "hatchback",
              {"cubierta_tras_der": ("Malo", 70000, "Gastada"),
               "tapizados": ("Regular", 60000, "Desgaste en asiento conductor")},
              "Usado que entrega Roberto Giménez como parte de pago.", "Bueno", "Regular", 7200000, 130000, 6100000, 970000, 2)

    # Ventas
    cur = conn.execute(
        """INSERT INTO ventas (agencia_id, vehiculo_id, estado, estado_previo, cliente_nombre, cliente_telefono,
               precio_venta, sena, fecha_sena, contado_previsto, observaciones, sucursal_id)
           VALUES (?,?, 'senado', 'disponible', 'Marcelo Fernández', '5493415550301', 17500000, 1500000, ?, 16000000,
                   'Pasa a retirarlo el viernes con el resto en efectivo.', ?)""",
        (demo_id, vid["vento"], iso(hoy - timedelta(days=3)), suc_ids[0]))
    conn.execute("UPDATE vehiculos SET estado='senado' WHERE id=?", (vid["vento"],))
    conn.execute(
        """INSERT INTO ventas (agencia_id, vehiculo_id, estado, estado_previo, cliente_nombre, cliente_telefono,
               precio_venta, sena, fecha_sena, efectivo_cobrado, fecha_venta, sucursal_id)
           VALUES (?,?, 'cerrada', 'disponible', 'Gustavo Peralta', '5493415550302', 23500000, 2000000, ?, 23500000, ?, ?)""",
        (demo_id, vid["hrv"], iso(hoy - timedelta(days=16)), iso(hoy - timedelta(days=12)), suc_ids[0]))
    conn.execute("UPDATE vehiculos SET valor_vendido=23500000 WHERE id=?", (vid["hrv"],))

    # Financiación 1: Frontier, plan activo (con una cuota atrasada)
    inicio = hoy - timedelta(days=65)
    monto, tasa, n = 10000000, 5, 12
    cuota = round((monto + monto * tasa / 100 * n) / n)
    fid = conn.execute(
        """INSERT INTO financiaciones (agencia_id, vehiculo_id, cliente_nombre, cliente_telefono, precio_venta, anticipo,
               monto_financiado, tasa_interes_mensual, tasa_interes_punitorio, metodo_interes, periodicidad, plazo_meses,
               cantidad_cuotas, valor_cuota, fecha_inicio, estado, observaciones, cliente_dni, cliente_domicilio, sucursal_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'activo',?,?,?,?)""",
        (demo_id, vid["frontier"], "Ariel Domínguez", "5493415550303", 25500000, 15500000, monto, tasa, 10, "simple",
         "mensual", n, n, cuota, iso(inicio), "Plan de ejemplo con una cuota atrasada.", "30456789",
         "Mitre 850, Rosario", suc_ids[0])).lastrowid
    for numero in range(1, n + 1):
        venc = _meses(inicio, numero - 1)
        pagada = numero <= 2
        conn.execute(
            """INSERT INTO financiacion_cuotas (financiacion_id, numero, fecha_vencimiento, monto, monto_pagado, fecha_pago, estado)
               VALUES (?,?,?,?,?,?,?)""",
            (fid, numero, iso(venc), cuota, cuota if pagada else 0, iso(venc) if pagada else None,
             "pagada" if pagada else "pendiente"))
    conn.execute("UPDATE vehiculos SET valor_vendido=25500000 WHERE id=?", (vid["frontier"],))
    conn.execute("INSERT INTO garantes (financiacion_id, nombre, dni, telefono, domicilio) VALUES (?,?,?,?,?)",
                 (fid, "Silvia Domínguez", "27111222", "5493415550304", "Mitre 850, Rosario"))

    # Financiación 2: Onix, crédito en trámite (pendiente de firma) con garantes
    monto2, tasa2, n2 = 6000000, 4.5, 18
    cuota2 = round((monto2 + monto2 * tasa2 / 100 * n2) / n2)
    inicio2 = hoy + timedelta(days=15)
    fid2 = conn.execute(
        """INSERT INTO financiaciones (agencia_id, vehiculo_id, cliente_nombre, cliente_telefono, precio_venta, anticipo,
               monto_financiado, tasa_interes_mensual, tasa_interes_punitorio, metodo_interes, periodicidad, plazo_meses,
               cantidad_cuotas, valor_cuota, fecha_inicio, estado, observaciones, cliente_dni, cliente_domicilio, creado_por_id, sucursal_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'pendiente_firma',?,?,?,NULL,?)""",
        (demo_id, vid["onix"], "Nahuel Gaitán", "5493415550305", 13900000, 7900000, monto2, tasa2, 10, "simple",
         "mensual", n2, n2, cuota2, iso(inicio2), "Esperando que vengan los garantes a firmar.", "38222333",
         "San Luis 1520, Rosario", suc_ids[1])).lastrowid
    for numero in range(1, n2 + 1):
        conn.execute(
            """INSERT INTO financiacion_cuotas (financiacion_id, numero, fecha_vencimiento, monto, monto_pagado, estado)
               VALUES (?,?,?,?,0,'pendiente')""", (fid2, numero, iso(_meses(inicio2, numero - 1)), cuota2))
    for nombre, dni, tel, dom in (("José Ricardo Cortez", "25648634", "5493415550306", "Dalia Lama 322"),
                                  ("Martín Ezequiel Rotela", "29680263", None, None)):
        conn.execute("INSERT INTO garantes (financiacion_id, nombre, dni, telefono, domicilio) VALUES (?,?,?,?,?)",
                     (fid2, nombre, dni, tel, dom))

    # Red: publicaciones de las agencias ficticias
    for (idx, tipo, marca, modelo, version, anio, km, precio, desc) in RED_PUBLICACIONES:
        nombre, tel = RED_AGENCIAS[idx]
        conn.execute(
            """INSERT INTO red_publicaciones (agencia_id, agencia_nombre, tipo, marca, modelo, version, anio, km, precio,
                   descripcion, contacto, estado, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?, 'activo', ?)""",
            (red_ids[idx], nombre, tipo, marca, modelo, version, anio, km, precio, desc,
             f"{nombre} · {tel}", f"{hoy - timedelta(days=(idx * 2 + 1))} 10:00:00"))
    # …y unidades de la demo publicadas en la Red
    for v in VEHICULOS:
        if v[15]:
            clave, marca, modelo, version, anio, km = v[0], v[1], v[2], v[3], v[4], v[5]
            conn.execute(
                """INSERT INTO red_publicaciones (agencia_id, agencia_nombre, tipo, marca, modelo, version, anio, km, precio,
                       descripcion, contacto, estado, vehiculo_id)
                   VALUES (?,?, 'ofrezco', ?,?,?,?,?,?, 'Unidad de la agencia demo.', ?, 'activo', ?)""",
                (demo_id, NOMBRE_DEMO, marca, modelo, version, anio, km, v[13], f"{NOMBRE_DEMO} · 5493410000000", vid[clave]))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fotos":
        generar_fotos(forzar=True)
        print("Fotos regeneradas en", CARPETA_FOTOS)
    else:
        from database import init_db
        init_db()
        print("Demo reiniciada. Agencia id:", reiniciar_demo())
