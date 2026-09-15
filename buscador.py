"""Buscador compartido por Marca / Modelo / Versión / Año / Km / Rango de
precio — mismo criterio y mismos nombres de campo en Stock (pestañas
Disponible, Por ingresar, En reparación) y en Red de Agencieros, para que
sea un único buscador reutilizado en vez de dos implementaciones separadas
(pedido de Daniel 15/09/2026, continuación 17)."""

CAMPOS_BASE = ["marca", "modelo", "version", "anio", "precio_min", "precio_max"]


def filtros_busqueda(args, campo_precio="valor_publicado", campo_km="km", incluir_km=False):
    """Lee los parámetros de búsqueda desde `request.args` (o cualquier dict
    tipo `args.get`), y arma:
    - `filtros`: solo los campos con valor cargado (para repoblar el form y
      para no perderlos al cambiar de pestaña / tipo).
    - `condiciones` / `params`: listos para un WHERE armado a mano (`" AND
      ".join(condiciones)`), sobre la tabla que llame a esta función —
      `campo_precio` y `campo_km` existen porque Stock usa `valor_publicado`
      y Red usa `precio`, y Red no tiene columna de Km.

    Marca/Modelo/Versión buscan por coincidencia parcial (LIKE, sin importar
    mayúsculas/minúsculas por el collate por default de SQLite en texto
    ASCII), Año es exacto, Km es "hasta" (kilometraje máximo) y el precio es
    un rango con mínimo y/o máximo opcionales."""
    campos = list(CAMPOS_BASE)
    if incluir_km:
        campos.append("km_max")

    filtros = {c: (args.get(c) or "").strip() for c in campos}
    filtros = {k: v for k, v in filtros.items() if v}

    # Importante: primero se intenta convertir el número y recién si sale
    # bien se agregan condición + parámetro juntos — si el append de la
    # condición fuera antes del int() y este tirara ValueError, quedaba una
    # condición "huérfana" sin su parámetro y sqlite3 rompía con
    # "Incorrect number of bindings supplied" (bug encontrado y corregido
    # en la verificación de esta misma sesión).
    condiciones, params = [], []
    if filtros.get("marca"):
        condiciones.append("marca LIKE ?")
        params.append(f"%{filtros['marca']}%")
    if filtros.get("modelo"):
        condiciones.append("modelo LIKE ?")
        params.append(f"%{filtros['modelo']}%")
    if filtros.get("version"):
        condiciones.append("version LIKE ?")
        params.append(f"%{filtros['version']}%")
    if filtros.get("anio"):
        try:
            valor = int(filtros["anio"])
        except ValueError:
            filtros.pop("anio", None)
        else:
            condiciones.append("anio = ?")
            params.append(valor)
    if incluir_km and filtros.get("km_max"):
        try:
            valor = int(filtros["km_max"])
        except ValueError:
            filtros.pop("km_max", None)
        else:
            condiciones.append(f"{campo_km} <= ?")
            params.append(valor)
    if filtros.get("precio_min"):
        try:
            valor = float(filtros["precio_min"])
        except ValueError:
            filtros.pop("precio_min", None)
        else:
            condiciones.append(f"{campo_precio} >= ?")
            params.append(valor)
    if filtros.get("precio_max"):
        try:
            valor = float(filtros["precio_max"])
        except ValueError:
            filtros.pop("precio_max", None)
        else:
            condiciones.append(f"{campo_precio} <= ?")
            params.append(valor)

    return filtros, condiciones, params
