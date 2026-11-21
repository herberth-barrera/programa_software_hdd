import base64
import hmac
import json
import os
import re
import secrets
import time
from functools import wraps
from urllib.parse import urlencode

import requests
from flask import abort, request, session
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

PASSWORD_INICIAL = "123456789"
DOMINIO_RRHH_POR_DEFECTO = "keyinstitute.edu.sv"
MAX_INTENTOS = 5
MINUTOS_BLOQUEO = 10


# ---------- Configuración (.env) ----------
def cargar_env(ruta):
    """Lee un archivo .env sencillo (CLAVE=valor) sin pisar variables que ya existan."""
    if not os.path.isfile(ruta):
        return
    with open(ruta, encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def config_microsoft():
    """Datos de la app registrada en Microsoft Entra. Devuelve None si falta alguno."""
    cfg = {
        "cliente": os.environ.get("MS_CLIENT_ID", ""),
        "tenant": os.environ.get("MS_TENANT_ID", ""),
        "secreto": os.environ.get("MS_CLIENT_SECRET", ""),
        "redireccion": os.environ.get("MS_REDIRECT_URI", "http://localhost:5000/auth/microsoft/callback"),
        "dominio": os.environ.get("RRHH_DOMINIO", DOMINIO_RRHH_POR_DEFECTO).lower().lstrip("@"),
    }
    if not (cfg["cliente"] and cfg["tenant"] and cfg["secreto"]):
        return None
    return cfg


# ---------- Contraseñas ----------
def hash_password(clave):
    return generate_password_hash(clave)


def verificar_password(hash_guardado, clave):
    return check_password_hash(hash_guardado, clave)


# Hash de relleno para que un código inexistente tarde lo mismo que uno real
_HASH_RELLENO = generate_password_hash("relleno-sin-uso")


def verificar_relleno(clave):
    check_password_hash(_HASH_RELLENO, clave)


def validar_password_nueva(nueva, codigo):
    if len(nueva) < 8:
        return "La contraseña debe tener al menos 8 caracteres."
    if not re.search(r"[A-Za-z]", nueva) or not re.search(r"\d", nueva):
        return "La contraseña debe combinar letras y números."
    if nueva == PASSWORD_INICIAL or nueva.upper() == codigo.upper():
        return "Elige una contraseña distinta a la inicial y a tu código."
    return ""


# ---------- CSRF ----------
def token_csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def campo_csrf():
    return Markup('<input type="hidden" name="csrf_token" value="%s">' % token_csrf())


def csrf_valido():
    enviado = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
    esperado = session.get("csrf", "")
    return bool(esperado) and hmac.compare_digest(enviado, esperado)


# ---------- Roles ----------
def solo_rrhh(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if session.get("rol") != "rrhh":
            abort(403)
        return vista(*args, **kwargs)
    return envoltura


def solo_empleado(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if session.get("rol") != "empleado":
            abort(403)
        return vista(*args, **kwargs)
    return envoltura


def quien_actua():
    """Texto y rol de quien hace un cambio, para el historial."""
    if session.get("rol") == "rrhh":
        return session.get("correo", "RRHH"), "rrhh"
    return session.get("codigo", "empleado"), "empleado"


# ---------- Inicio de sesión con Microsoft (OAuth 2.0 / OpenID Connect) ----------
def url_inicio_microsoft(cfg):
    estado = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    session["ms_estado"] = estado
    session["ms_nonce"] = nonce
    parametros = {
        "client_id": cfg["cliente"],
        "response_type": "code",
        "redirect_uri": cfg["redireccion"],
        "response_mode": "query",
        "scope": "openid profile email",
        "state": estado,
        "nonce": nonce,
        "prompt": "select_account",
    }
    return "https://login.microsoftonline.com/%s/oauth2/v2.0/authorize?%s" % (
        cfg["tenant"], urlencode(parametros))


def _leer_claims(id_token):
    try:
        cuerpo = id_token.split(".")[1]
        cuerpo += "=" * (-len(cuerpo) % 4)
        return json.loads(base64.urlsafe_b64decode(cuerpo.encode()))
    except (IndexError, ValueError):
        return None


def completar_login_microsoft(cfg, argumentos):
    """Cambia el código de Microsoft por la identidad. Devuelve (datos, error)."""
    esperado = session.pop("ms_estado", "")
    nonce = session.pop("ms_nonce", "")
    if argumentos.get("error"):
        return None, "Microsoft canceló o rechazó el inicio de sesión."
    if not esperado or not hmac.compare_digest(argumentos.get("state", ""), esperado):
        return None, "La solicitud de inicio de sesión no es válida o expiró. Inténtalo de nuevo."
    codigo = argumentos.get("code", "")
    if not codigo:
        return None, "Microsoft no devolvió el código de autorización."

    try:
        respuesta = requests.post(
            "https://login.microsoftonline.com/%s/oauth2/v2.0/token" % cfg["tenant"],
            data={"client_id": cfg["cliente"], "client_secret": cfg["secreto"], "code": codigo,
                  "grant_type": "authorization_code", "redirect_uri": cfg["redireccion"],
                  "scope": "openid profile email"},
            timeout=15)
        respuesta = respuesta.json()
    except (requests.RequestException, ValueError):
        return None, "No se pudo contactar con Microsoft. Revisa tu conexión a internet."
    if "id_token" not in respuesta:
        return None, "Microsoft no aceptó el inicio de sesión. Revisa el secreto de cliente en el archivo .env."

    # El token llega directo desde Microsoft por HTTPS y autenticado con el secreto de la app,
    # por eso aquí se validan sus datos sin volver a verificar la firma.
    claims = _leer_claims(respuesta["id_token"])
    if not claims:
        return None, "La respuesta de Microsoft no se pudo interpretar."
    if claims.get("aud") != cfg["cliente"] or claims.get("tid") != cfg["tenant"]:
        return None, "La cuenta no pertenece a la organización autorizada."
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce or "-"):
        return None, "La respuesta de Microsoft no coincide con la solicitud."
    if int(claims.get("exp", 0)) < time.time():
        return None, "La sesión de Microsoft expiró. Inténtalo de nuevo."

    correo = (claims.get("preferred_username") or claims.get("email") or "").strip().lower()
    if not correo.endswith("@" + cfg["dominio"]):
        return None, "Solo las cuentas @%s pueden entrar como RRHH." % cfg["dominio"]
    return {"correo": correo, "nombre": claims.get("name") or correo}, ""
