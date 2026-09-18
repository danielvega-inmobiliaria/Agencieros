"""Panel de Agencias (18/09/2026).

Vista de plataforma para Daniel (agencia_id=1, el dueño de AGENCIEROS) --
no es un módulo de negocio de ninguna agencia en particular, sino el
"pulso" del sector: quiénes son las agencias registradas, dónde están, y
cuánto están usando la app (stock, ventas, financiación). Pensado para
cuando empiecen a sumarse agencias reales a la Red -- hoy con 1-2 agencias
de prueba sirve igual para dejar el panel armado y probado de antemano.

Acceso: gateado en app.py (MODULOS_SOLO_AGENCIA_1) -- solo la agencia 1
puede ver esto, igual que Dashboard/Finanzas/Tomas/Financiación.
"""

from flask import Blueprint, render_template

from database import query

bp = Blueprint("plataforma", __name__, url_prefix="/plataforma")


@bp.route("/agencias")
def agencias():
    agencias_rows = query(
        """SELECT a.id, a.nombre_agencia, a.email, a.telefono AS telefono_registro,
                  a.email_verificado, a.activo, a.created_at,
                  c.telefono AS telefono_comercial, c.direccion, c.ciudad, c.provincia
           FROM agencias a
           LEFT JOIN agencia_config c ON c.agencia_id = a.id
           ORDER BY a.id ASC"""
    )

    stock_rows = query(
        """SELECT agencia_id,
                  SUM(CASE WHEN estado = 'disponible' THEN 1 ELSE 0 END) AS disponibles,
                  SUM(CASE WHEN estado = 'por_ingresar' THEN 1 ELSE 0 END) AS por_ingresar,
                  SUM(CASE WHEN estado = 'en_reparacion' THEN 1 ELSE 0 END) AS en_reparacion,
                  SUM(CASE WHEN estado = 'vendido' THEN 1 ELSE 0 END) AS ventas_totales,
                  SUM(CASE WHEN estado = 'vendido'
                           AND strftime('%Y-%m', fecha_venta) = strftime('%Y-%m', 'now')
                      THEN 1 ELSE 0 END) AS ventas_mes
           FROM vehiculos
           GROUP BY agencia_id"""
    )
    stock_por_agencia = {r["agencia_id"]: r for r in stock_rows}

    credito_rows = query(
        """SELECT agencia_id, COUNT(*) AS cantidad, COALESCE(SUM(monto_financiado), 0) AS monto_total
           FROM financiaciones
           GROUP BY agencia_id"""
    )
    credito_por_agencia = {r["agencia_id"]: r for r in credito_rows}

    filas = []
    for a in agencias_rows:
        s = stock_por_agencia.get(a["id"])
        c = credito_por_agencia.get(a["id"])
        filas.append({
            "id": a["id"],
            "nombre": a["nombre_agencia"],
            "email": a["email"],
            "telefono": a["telefono_comercial"] or a["telefono_registro"],
            "direccion": a["direccion"],
            "ciudad": a["ciudad"],
            "provincia": a["provincia"],
            "verificada": bool(a["email_verificado"]),
            "activa": bool(a["activo"]),
            "alta": a["created_at"],
            "disponibles": (s["disponibles"] if s else 0) or 0,
            "por_ingresar": (s["por_ingresar"] if s else 0) or 0,
            "en_reparacion": (s["en_reparacion"] if s else 0) or 0,
            "ventas_mes": (s["ventas_mes"] if s else 0) or 0,
            "ventas_totales": (s["ventas_totales"] if s else 0) or 0,
            "creditos_cantidad": (c["cantidad"] if c else 0) or 0,
            "creditos_monto": (c["monto_total"] if c else 0) or 0,
        })

    resumen = {
        "total_agencias": len(filas),
        "verificadas": sum(1 for f in filas if f["verificada"]),
        "ventas_mes_total": sum(f["ventas_mes"] for f in filas),
        "creditos_monto_total": sum(f["creditos_monto"] for f in filas),
    }

    return render_template("plataforma/agencias.html", filas=filas, resumen=resumen)
