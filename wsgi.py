"""Punto de entrada WSGI para publicar el sistema en un hosting (alwaysdata)."""
import os
import sys

# El hosting puede arrancar el programa desde otra carpeta: se asegura que se encuentren app.py y los demás módulos
CARPETA = os.path.dirname(os.path.abspath(__file__))
if CARPETA not in sys.path:
    sys.path.insert(0, CARPETA)
os.chdir(CARPETA)

from app import app as application  # noqa: E402
