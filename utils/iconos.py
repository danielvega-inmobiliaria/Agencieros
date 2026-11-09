"""Ícono / favicon según la agencia (09/11/2026): Italia Automotores usa su logo; el resto, el de Agencieros."""
import os


def icono_de_agencia(agencia_id):
    italia = int(os.environ.get("STOCK_SYNC_AGENCIA_ID", "1"))
    return "italia" if agencia_id and int(agencia_id) == italia else "agencieros"
