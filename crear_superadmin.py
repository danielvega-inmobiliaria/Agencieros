"""Crea el administrador de la plataforma AGENCIEROS, o le cambia la
contraseña si ya existe (28/09/2026).

Uso (en la carpeta del proyecto):
    python crear_superadmin.py mail@ejemplo.com "contraseña"

En Railway alcanza con cargar las variables SUPERADMIN_EMAIL y
SUPERADMIN_PASSWORD: se crea solo al arrancar si todavía no hay ninguno.
"""
import sqlite3
import sys

from database import DB_PATH, init_db, crear_o_actualizar_superadmin


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    init_db()
    conn = sqlite3.connect(DB_PATH)
    print(crear_o_actualizar_superadmin(conn, sys.argv[1], sys.argv[2]))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
