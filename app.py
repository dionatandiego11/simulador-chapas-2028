"""Entrada principal do simulador, compartilhada com o script iniciar.sh."""

from pathlib import Path
import runpy
import sys

pasta_app = Path(__file__).resolve().parent / "simulador_chapas_2028"
if str(pasta_app) not in sys.path:
    sys.path.insert(0, str(pasta_app))
runpy.run_path(str(pasta_app / "app_2028.py"), run_name="__main__")
