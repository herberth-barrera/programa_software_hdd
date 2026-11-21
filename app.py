import os
import secrets
import shutil
import socket
import tempfile
import time
import uuid
from datetime import datetime, date, timedelta
from urllib.parse import quote

import mysql.connector
from flask import Flask, render_template, request, redirect, abort, Response, flash, session

import seguridad as seg
from expediente_pdf import construir_expediente, ErrorExpediente

# Variables privadas (secreto de Microsoft, clave de sesión) desde el archivo .env
CARPETA = os.path.dirname(os.path.abspath(__file__))
seg.cargar_env(os.path.join(CARPETA, ".env"))

app = Flask(__name__)
app.secret_key = os.environ.get("HDD_SECRET_KEY") or secrets.token_hex(32)
app.permanent_session_lifetime = timedelta(hours=8)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
app.jinja_env.globals["campo_csrf"] = seg.campo_csrf

# Menu Desplegable
SUCURSALES = ["Escalón", "Santa Elena", "Colonia Médica"]
ESTADOS = ["Activo", "Inactivo", "Licencia médica", "Vacaciones"]
ESTADOS_CIVILES = ["Soltero/a", "Casado/a", "Acompañado/a", "Divorciado/a", "Viudo/a"]
AREAS = [
    "Admisión", "Archivo clínico", "Cardiología", "Consulta externa", "Emergencias",
    "Farmacia", "Imagenología", "Laboratorio", "Mantenimiento", "Nutrición",
    "Quirófano", "Recursos humanos", "Talento Humano", "Tecnología", "Administración",
    "Limpieza y servicios generales",
]
PUESTOS = [
    "Médico/a general", "Médico/a especialista", "Radiólogo/a", "Cardiólogo/a", "Enfermero/a",
    "Auxiliar de enfermería", "Técnico/a de laboratorio", "Técnico/a en radiología",
    "Farmacéutico/a", "Nutricionista", "Recepcionista", "Cajero/a", "Asistente administrativo/a",
    "Analista de talento humano", "Contador/a", "Técnico/a de sistemas", "Archivista",
    "Camillero/a", "Personal de limpieza", "Personal de mantenimiento", "Seguridad",
    "Gerente de área", "Director/a médico/a", "Psicólogo/a", "Fisioterapeuta", "Anestesiólogo/a",
]
CLASE_ESTADO = {"Activo": "activo", "Inactivo": "inactivo",
                "Licencia médica": "licencia", "Vacaciones": "vacaciones"}
ETIQUETAS = {
    "nombre": "Nombre", "puesto": "Puesto", "area": "Área", "sucursal": "Sucursal",
    "estado": "Estado laboral", "fecha_ingreso": "Fecha de ingreso",
    "fecha_nacimiento": "Fecha de nacimiento", "estado_civil": "Estado civil", "direccion": "Dirección",
}
CAMPOS_RRHH = ["nombre", "puesto", "area", "sucursal", "estado", "fecha_ingreso",
               "fecha_nacimiento", "estado_civil", "direccion"]
CAMPOS_EMPLEADO = ["fecha_nacimiento", "estado_civil", "direccion"]

PREFIJO_CODIGO = "HDD-"

# Subir Archivos (solo PDF)
EXTENSIONES_PERMITIDAS = (".pdf",)
MAX_BYTES = 1024 ** 3          # 1 GB por documento
TAMANO_PARTE = 256 * 1024      # cada pedazo que se guarda en la base de datos
app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES + 8 * 1024 * 1024

# XAMPP
SERVICIOS = [("Apache", "127.0.0.1", 80), ("MySQL", "127.0.0.1", 3306)]
_cache_servicios = {"hora": 0.0, "caidos": []}

# Rutas que se pueden abrir sin haber iniciado sesión
PUBLICAS = {"static", "login", "microsoft_inicio", "microsoft_callback"}


def conectar():
    # En XAMPP el usuario es root y la contraseña va vacía
    return mysql.connector.connect(host="localhost", user="root", password="",
                                   database="hospital_hdd", charset="utf8mb4")


def puerto_abierto(host, puerto):
    try:
        with socket.create_connection((host, puerto), timeout=0.6):
            return True
    except OSError:
        return False


def servicios_caidos():
    # Se revisa como mucho una vez por segundo para no frenar cada petición
    ahora = time.time()
    if ahora - _cache_servicios["hora"] > 1:
        _cache_servicios["caidos"] = [n for n, h, p in SERVICIOS if not puerto_abierto(h, p)]
        _cache_servicios["hora"] = ahora
    return _cache_servicios["caidos"]


# ---------- Filtros que se ejecutan antes de cada petición (en este orden) ----------
@app.before_request
def verificar_servicios():
    if request.endpoint == "static":
        return None
    caidos = servicios_caidos()
    if caidos:
        estado = [{"nombre": n, "puerto": p, "activo": n not in caidos} for n, h, p in SERVICIOS]
        return render_template("servicios.html", servicios=estado), 503
    return None


@app.before_request
def usar_localhost():
    # Microsoft compara la dirección de regreso letra por letra: se entra siempre por localhost
    if request.method == "GET" and request.host.split(":")[0] == "127.0.0.1":
        puerto = request.host.split(":")[1] if ":" in request.host else "80"
        return redirect("http://localhost:%s%s" % (puerto, request.full_path.rstrip("?")))
    return None


@app.before_request
def controlar_acceso():
    if request.endpoint is None or request.endpoint == "static":
        return None
    if request.method == "POST" and not seg.csrf_valido():
        return render_template("error.html", titulo="Sesión no válida",
                               mensaje="El formulario caducó o no es válido. Vuelve atrás, recarga la página "
                                       "e inténtalo de nuevo.", detalle=""), 400
    if request.endpoint in PUBLICAS:
        return None
    if "rol" not in session:
        return redirect("/login")
    # Mientras tenga la contraseña inicial, solo puede cambiarla o cerrar sesión
    if session.get("debe_cambiar") and request.endpoint not in ("cambiar_password", "logout"):
        return redirect("/cuenta/password")
    return None


@app.after_request
def cabeceras(respuesta):
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "SAMEORIGIN"
    if request.endpoint != "static":
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


# ---------- Utilidades ----------
def formato_tamano(n):
    if n >= 1024 ** 3:
        return "%.2f GB" % (n / 1024 ** 3)
    if n >= 1024 ** 2:
        valor = n / 1024 ** 2
        return ("%d MB" % valor) if valor == int(valor) else ("%.1f MB" % valor)
    if n >= 1024:
        return "%d KB" % (n // 1024)
    return "%d B" % n


@app.template_filter("iniciales")
def iniciales(nombre):
    partes = nombre.split()
    if not partes:
        return "?"
    return (partes[0][0] + (partes[-1][0] if len(partes) > 1 else "")).upper()


@app.template_filter("clase_estado")
def clase_estado(estado):
    return CLASE_ESTADO.get(estado, "inactivo")


@app.template_filter("fecha")
def formato_fecha(valor):
    return valor.strftime("%d/%m/%Y") if valor else "—"


@app.template_filter("fecha_hora")
def formato_fecha_hora(valor):
    return valor.strftime("%d/%m/%Y %H:%M") if valor else "—"


def con_actual(lista, actual):
    """Si el valor guardado ya no está en la lista, se agrega para no perderlo al editar."""
    return lista if actual in lista else [actual] + lista


def texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, (date, datetime)):
        return valor.strftime("%Y-%m-%d")
    return str(valor)


def diferencias(antes, despues, campos):
    """Lista de (campo, valor anterior, valor nuevo) solo de lo que realmente cambió."""
    cambios = []
    for campo in campos:
        if texto(antes.get(campo)) != texto(despues.get(campo)):
            cambios.append((ETIQUETAS[campo], texto(antes.get(campo)), texto(despues.get(campo))))
    return cambios


def registrar_cambios(cursor, emp_id, tipo, cambios):
    """Guarda en el historial un renglón por cambio, dentro de la misma transacción del cambio."""
    actor, rol = seg.quien_actua()
    lote = uuid.uuid4().hex
    for campo, antes, despues in cambios:
        cursor.execute(
            "INSERT INTO historial_cambios (empleado_id, lote, actor, rol_actor, tipo, campo, "
            "valor_anterior, valor_nuevo) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (emp_id, lote, actor, rol, tipo, campo, antes or None, despues or None))


def fecha_valida(valor):
    try:
        datetime.strptime(valor, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validar_personales(datos, obligatorios):
    """Valida fecha de nacimiento, estado civil y dirección. Devuelve el mensaje de error o ''."""
    if obligatorios and "" in (datos["fecha_nacimiento"], datos["estado_civil"], datos["direccion"]):
        return "Completa tu fecha de nacimiento, estado civil y dirección."
    if datos["fecha_nacimiento"]:
        if not fecha_valida(datos["fecha_nacimiento"]):
            return "La fecha de nacimiento no es válida."
        nacimiento = datetime.strptime(datos["fecha_nacimiento"], "%Y-%m-%d").date()
        if nacimiento > date.today() or nacimiento.year < 1920:
            return "La fecha de nacimiento no es posible."
    if datos["estado_civil"] and datos["estado_civil"] not in ESTADOS_CIVILES:
        return "Selecciona un estado civil de la lista."
    if len(datos["direccion"]) > 255:
        return "La dirección es demasiado larga (máximo 255 caracteres)."
    return ""


def cargar_empleado(cursor, emp_id):
    cursor.execute("SELECT * FROM empleados WHERE id = %s", (emp_id,))
    empleado = cursor.fetchone()
    if empleado is None:
        cursor.close()
        abort(404)
    return empleado


def perfil_completo(empleado):
    return bool(empleado["fecha_nacimiento"] and empleado["estado_civil"] and empleado["direccion"])


def siguiente_codigo(cursor):
    """Devuelve HDD-0007, HDD-0008... El contador solo avanza, así que un código borrado no se repite."""
    while True:
        cursor.execute("UPDATE secuencia_codigos SET ultimo = ultimo + 1 WHERE nombre = 'empleado'")
        cursor.execute("SELECT ultimo FROM secuencia_codigos WHERE nombre = 'empleado'")
        codigo = "%s%04d" % (PREFIJO_CODIGO, cursor.fetchone()["ultimo"])
        # Por si alguien insertó un código a mano en la base: se sigue avanzando hasta uno libre
        cursor.execute("SELECT id FROM empleados WHERE codigo = %s", (codigo,))
        if not cursor.fetchone():
            return codigo


def crear_cuenta(cursor, emp_id):
    cursor.execute("INSERT INTO usuarios (empleado_id, password_hash, debe_cambiar) VALUES (%s, %s, 1)",
                   (emp_id, seg.hash_password(seg.PASSWORD_INICIAL)))


def obtener_empleados():
    """Empleados con sus archivos subidos y sus documentos vencidos (el checklist sale de los archivos)."""
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.*,
               (SELECT COUNT(*) FROM documentos) AS total,
               (SELECT COUNT(DISTINCT a.documento_id) FROM archivos a
                WHERE a.empleado_id = e.id) AS con_archivo,
               (SELECT COUNT(*) FROM archivos a
                WHERE a.empleado_id = e.id AND a.fecha_vencimiento < CURDATE()
                  AND a.version = (SELECT MAX(a2.version) FROM archivos a2
                                   WHERE a2.empleado_id = a.empleado_id
                                     AND a2.documento_id = a.documento_id)) AS vencidos
        FROM empleados e
        ORDER BY e.id
    """)
    filas = cursor.fetchall()
    cursor.close()
    conexion.close()
    return filas


def texto_dias(n):
    return "1 día" if n == 1 else "%d días" % n


def datos_documentos(cursor, emp_id):
    """Archivos agrupados por documento (con versiones), checklist y resumen. Lo usan RRHH y el empleado."""
    cursor.execute("""
        SELECT a.id, a.documento_id, d.nombre AS documento, a.version, a.nombre_original,
               a.tamano, a.fecha_vencimiento, a.fecha_subida
        FROM archivos a JOIN documentos d ON d.id = a.documento_id
        WHERE a.empleado_id = %s
        ORDER BY d.id, a.version DESC
    """, (emp_id,))
    filas = cursor.fetchall()
    cursor.execute("SELECT id, nombre FROM documentos ORDER BY id")
    todos = cursor.fetchall()

    hoy = date.today()
    grupos = []
    por_documento = {}
    vigentes = 0
    vencidos = 0
    for fila in filas:
        # Vienen de la versión más nueva a la más vieja: la primera de cada documento es la vigente
        es_ultima = fila["documento_id"] not in por_documento
        vence = fila["fecha_vencimiento"]
        aviso = ""
        if not es_ultima:
            estado, clase = "Versión anterior", "anterior"
        elif vence is not None and vence < hoy:
            estado, clase = "Vencido", "vencido"
            aviso = "Venció hace " + texto_dias((hoy - vence).days)
            vencidos = vencidos + 1
        else:
            estado, clase = "Vigente", "vigente"
            if vence == hoy:
                aviso = "Vence hoy"
            elif vence is not None:
                aviso = "Vence en " + texto_dias((vence - hoy).days)
            vigentes = vigentes + 1
        es_pdf = os.path.splitext(fila["nombre_original"])[1].lower() == ".pdf"
        item = {"datos": fila, "estado": estado, "clase": clase, "aviso": aviso,
                "tamano": formato_tamano(fila["tamano"]), "es_pdf": es_pdf,
                "tipo": "pdf" if es_pdf else "word", "etiqueta": "PDF" if es_pdf else "DOC"}
        if es_ultima:
            grupo = {"documento_id": fila["documento_id"], "nombre": fila["documento"],
                     "ultima": item, "versiones": [item]}
            por_documento[fila["documento_id"]] = grupo
            grupos.append(grupo)
        else:
            por_documento[fila["documento_id"]]["versiones"].append(item)

    checklist = [{"id": d["id"], "nombre": d["nombre"], "subido": d["id"] in por_documento} for d in todos]
    pendientes = [c for c in checklist if not c["subido"]]
    resumen_archivos = {"subidos": len(grupos), "total": len(todos), "vigentes": vigentes,
                        "vencidos": vencidos, "pendientes": len(pendientes)}
    return grupos, checklist, pendientes, resumen_archivos


def leer_historial(cursor, emp_id):
    cursor.execute("""
        SELECT id, lote, actor, rol_actor, tipo, campo, valor_anterior, valor_nuevo, fecha
        FROM historial_cambios WHERE empleado_id = %s ORDER BY fecha DESC, id DESC
    """, (emp_id,))
    return cursor.fetchall()


# ---------- Inicio de sesión ----------
@app.route("/")
def inicio():
    if session.get("rol") == "rrhh":
        return redirect("/empleados")
    if session.get("rol") == "empleado":
        return redirect("/mi/expediente")
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("rol") and not session.get("debe_cambiar"):
        return redirect("/")
    acceso = "rrhh" if request.args.get("acceso") == "rrhh" else "empleado"
    error = ""
    codigo = ""
    if request.method == "POST":
        acceso = "empleado"
        codigo = request.form.get("codigo", "").strip().upper()
        clave = request.form.get("password", "")
        conexion = conectar()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT id, nombre, estado FROM empleados WHERE codigo = %s", (codigo,))
        empleado = cursor.fetchone()
        mensaje_general = "El código o la contraseña no son correctos."
        if empleado is None:
            seg.verificar_relleno(clave)
            error = mensaje_general
        else:
            cursor.execute("SELECT * FROM usuarios WHERE empleado_id = %s", (empleado["id"],))
            cuenta = cursor.fetchone()
            if cuenta is None:
                # Empleado que existía antes de los accesos: se le crea su cuenta inicial
                crear_cuenta(cursor, empleado["id"])
                conexion.commit()
                cursor.execute("SELECT * FROM usuarios WHERE empleado_id = %s", (empleado["id"],))
                cuenta = cursor.fetchone()
            ahora = datetime.now()
            if cuenta["bloqueado_hasta"] and cuenta["bloqueado_hasta"] > ahora:
                minutos = int((cuenta["bloqueado_hasta"] - ahora).total_seconds() // 60) + 1
                error = "Demasiados intentos fallidos. Intenta de nuevo en %d minuto(s)." % minutos
            elif not seg.verificar_password(cuenta["password_hash"], clave):
                intentos = cuenta["intentos_fallidos"] + 1
                bloqueo = None
                if intentos >= seg.MAX_INTENTOS:
                    bloqueo = ahora + timedelta(minutes=seg.MINUTOS_BLOQUEO)
                    intentos = 0
                cursor.execute("UPDATE usuarios SET intentos_fallidos = %s, bloqueado_hasta = %s WHERE id = %s",
                               (intentos, bloqueo, cuenta["id"]))
                conexion.commit()
                error = mensaje_general
            elif empleado["estado"] == "Inactivo":
                error = "Tu cuenta está inactiva. Comunícate con Recursos Humanos."
            else:
                cursor.execute("UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL, "
                               "ultimo_acceso = %s WHERE id = %s", (ahora, cuenta["id"]))
                conexion.commit()
                cursor.close()
                conexion.close()
                session.clear()
                session.permanent = True
                session.update(rol="empleado", empleado_id=empleado["id"], codigo=codigo,
                               nombre=empleado["nombre"], debe_cambiar=bool(cuenta["debe_cambiar"]))
                return redirect("/cuenta/password" if cuenta["debe_cambiar"] else "/mi/expediente")
        cursor.close()
        conexion.close()
    return render_template("login.html", acceso=acceso, error=error, codigo=codigo,
                           microsoft_listo=seg.config_microsoft() is not None)


@app.route("/auth/microsoft")
def microsoft_inicio():
    cfg = seg.config_microsoft()
    if cfg is None:
        flash("El acceso con Microsoft todavía no está configurado en el archivo .env.", "error")
        return redirect("/login?acceso=rrhh")
    return redirect(seg.url_inicio_microsoft(cfg))


@app.route("/auth/microsoft/callback")
def microsoft_callback():
    cfg = seg.config_microsoft()
    if cfg is None:
        return redirect("/login?acceso=rrhh")
    datos, error = seg.completar_login_microsoft(cfg, request.args)
    if error:
        flash(error, "error")
        return redirect("/login?acceso=rrhh")
    session.clear()
    session.permanent = True
    session.update(rol="rrhh", correo=datos["correo"], nombre=datos["nombre"], debe_cambiar=False)
    return redirect("/empleados")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/login")


@app.route("/cuenta/password", methods=["GET", "POST"])
@seg.solo_empleado
def cambiar_password():
    error = ""
    if request.method == "POST":
        actual = request.form.get("actual", "")
        nueva = request.form.get("nueva", "")
        repetida = request.form.get("repetida", "")
        conexion = conectar()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE empleado_id = %s", (session["empleado_id"],))
        cuenta = cursor.fetchone()
        if cuenta is None or not seg.verificar_password(cuenta["password_hash"], actual):
            error = "La contraseña actual no es correcta."
        elif nueva != repetida:
            error = "La confirmación no coincide con la nueva contraseña."
        elif nueva == actual:
            error = "La nueva contraseña debe ser distinta de la actual."
        else:
            error = seg.validar_password_nueva(nueva, session["codigo"])
        if not error:
            cursor.execute("UPDATE usuarios SET password_hash = %s, debe_cambiar = 0 WHERE id = %s",
                           (seg.hash_password(nueva), cuenta["id"]))
            registrar_cambios(cursor, session["empleado_id"], "cuenta",
                              [("Contraseña", "", "Actualizada por el empleado")])
            conexion.commit()
            session["debe_cambiar"] = False
            flash("Tu contraseña se actualizó.", "ok")
            cursor.close()
            conexion.close()
            return redirect("/mi/expediente")
        cursor.close()
        conexion.close()
    return render_template("cambiar_password.html", error=error, obligatorio=session.get("debe_cambiar"))


# ====================================================================
#   PORTAL DE RRHH
# ====================================================================

# Lista de empleados
@app.route("/empleados")
@seg.solo_rrhh
def listar():
    filas = obtener_empleados()
    empleados = []
    completos = 0
    con_vencidos = 0
    docs_subidos = 0
    docs_requeridos = 0
    for fila in filas:
        docs_subidos = docs_subidos + fila["con_archivo"]
        docs_requeridos = docs_requeridos + fila["total"]
        if fila["total"] > 0 and fila["con_archivo"] == fila["total"] and fila["vencidos"] == 0:
            estado, clase = "Completo", "completo"
            completos = completos + 1
        elif fila["vencidos"] > 0:
            estado, clase = "Con vencidos", "vencidos"
            con_vencidos = con_vencidos + 1
        else:
            estado, clase = "Incompleto", "incompleto"
        # Solo se puede eliminar un perfil que no tenga archivos subidos
        empleados.append({"datos": fila, "estado": estado, "clase": clase,
                          "eliminable": fila["con_archivo"] == 0})
    kpis = {"total": len(filas), "completos": completos, "con_vencidos": con_vencidos,
            "docs_subidos": docs_subidos, "docs_requeridos": docs_requeridos}
    return render_template("empleados.html", empleados=empleados, kpis=kpis)


# Registrar empleado
@app.route("/empleados/nuevo", methods=["GET", "POST"])
@seg.solo_rrhh
def nuevo():
    error = ""
    datos = {"nombre": "", "puesto": "", "area": "", "sucursal": "", "estado": "Activo", "fecha_ingreso": ""}
    if request.method == "POST":
        for campo in datos:
            datos[campo] = request.form.get(campo, "").strip()

        if "" in datos.values():
            error = "Todos los campos son obligatorios."
        elif datos["puesto"] not in PUESTOS:
            error = "Selecciona un puesto de la lista."
        elif datos["area"] not in AREAS:
            error = "Selecciona un área de la lista."
        elif datos["sucursal"] not in SUCURSALES:
            error = "Selecciona una sucursal válida."
        elif datos["estado"] not in ESTADOS:
            error = "Selecciona un estado válido."
        elif not fecha_valida(datos["fecha_ingreso"]):
            error = "La fecha de ingreso no es válida."
        else:
            conexion = conectar()
            cursor = conexion.cursor(dictionary=True)
            codigo = siguiente_codigo(cursor)
            cursor.execute(
                "INSERT INTO empleados (codigo, nombre, puesto, area, sucursal, estado, fecha_ingreso) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (codigo, datos["nombre"], datos["puesto"], datos["area"], datos["sucursal"],
                 datos["estado"], datos["fecha_ingreso"]))
            emp_id = cursor.lastrowid
            cursor.execute("SELECT id FROM documentos")
            for doc in cursor.fetchall():
                cursor.execute(
                    "INSERT INTO expediente (empleado_id, documento_id, entregado) VALUES (%s, %s, 0)",
                    (emp_id, doc["id"]))
            crear_cuenta(cursor, emp_id)
            registrar_cambios(cursor, emp_id, "perfil", [("Perfil", "", "Creado con el código " + codigo)])
            conexion.commit()
            cursor.close()
            conexion.close()
            flash("Empleado registrado con el código %s. Su contraseña inicial es %s y deberá cambiarla "
                  "al ingresar." % (codigo, seg.PASSWORD_INICIAL), "ok")
            return redirect("/empleados")
    return render_template("nuevo.html", error=error, datos=datos, sucursales=SUCURSALES,
                           puestos=PUESTOS, areas=AREAS, estados=ESTADOS)


# Perfil del empleado (panel de RRHH, solo lectura de documentos)
@app.route("/empleados/<int:emp_id>")
@seg.solo_rrhh
def perfil_rrhh(emp_id):
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    empleado = cargar_empleado(cursor, emp_id)
    grupos, checklist, pendientes, r = datos_documentos(cursor, emp_id)
    historial = leer_historial(cursor, emp_id)
    cursor.execute("SELECT debe_cambiar, ultimo_acceso FROM usuarios WHERE empleado_id = %s", (emp_id,))
    cuenta = cursor.fetchone()
    cursor.close()
    conexion.close()
    pestana = request.args.get("pestana", "datos")
    if pestana not in ("datos", "documentos", "historial"):
        pestana = "datos"
    return render_template("perfil_rrhh.html", empleado=empleado, grupos=grupos, checklist=checklist,
                           pendientes=pendientes, r=r, historial=historial, cuenta=cuenta,
                           pestana=pestana, completo=perfil_completo(empleado),
                           expediente_listo=(r["total"] > 0 and r["subidos"] == r["total"]))


@app.route("/empleados/<int:emp_id>/archivos")
@seg.solo_rrhh
def ver_archivos(emp_id):
    return redirect("/empleados/%d?pestana=documentos" % emp_id)


# Modificar Perfil
@app.route("/empleados/editar/<int:emp_id>", methods=["GET", "POST"])
@seg.solo_rrhh
def editar(emp_id):
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    empleado = cargar_empleado(cursor, emp_id)
    datos = {c: texto(empleado[c]) for c in CAMPOS_RRHH}
    error = ""
    if request.method == "POST":
        for campo in CAMPOS_RRHH:
            datos[campo] = request.form.get(campo, "").strip()
        obligatorios = ["nombre", "puesto", "area", "sucursal", "estado", "fecha_ingreso"]
        # Los valores que ya tenía el perfil se aceptan aunque hayan salido de la lista
        if any(datos[c] == "" for c in obligatorios):
            error = "Nombre, puesto, área, sucursal, estado y fecha de ingreso son obligatorios."
        elif datos["puesto"] not in con_actual(PUESTOS, empleado["puesto"]):
            error = "Selecciona un puesto de la lista."
        elif datos["area"] not in con_actual(AREAS, empleado["area"]):
            error = "Selecciona un área de la lista."
        elif datos["sucursal"] not in con_actual(SUCURSALES, empleado["sucursal"]):
            error = "Selecciona una sucursal válida."
        elif datos["estado"] not in ESTADOS:
            error = "Selecciona un estado válido."
        elif not fecha_valida(datos["fecha_ingreso"]):
            error = "La fecha de ingreso no es válida."
        else:
            error = validar_personales(datos, obligatorios=False)
        if not error:
            cambios = diferencias(empleado, datos, CAMPOS_RRHH)
            if cambios:
                # El código nunca se modifica
                cursor.execute(
                    "UPDATE empleados SET nombre = %s, puesto = %s, area = %s, sucursal = %s, estado = %s, "
                    "fecha_ingreso = %s, fecha_nacimiento = %s, estado_civil = %s, direccion = %s WHERE id = %s",
                    (datos["nombre"], datos["puesto"], datos["area"], datos["sucursal"], datos["estado"],
                     datos["fecha_ingreso"], datos["fecha_nacimiento"] or None, datos["estado_civil"] or None,
                     datos["direccion"] or None, emp_id))
                registrar_cambios(cursor, emp_id, "perfil", cambios)
                conexion.commit()
                flash("Se guardaron %d cambio(s) en el perfil %s." % (len(cambios), empleado["codigo"]), "ok")
            else:
                flash("No hubo cambios que guardar.", "ok")
            cursor.close()
            conexion.close()
            return redirect("/empleados/%d" % emp_id)
    cursor.close()
    conexion.close()
    return render_template("editar.html", empleado=empleado, error=error, datos=datos,
                           sucursales=con_actual(SUCURSALES, empleado["sucursal"]),
                           puestos=con_actual(PUESTOS, empleado["puesto"]),
                           areas=con_actual(AREAS, empleado["area"]), estados=ESTADOS,
                           estados_civiles=ESTADOS_CIVILES)


@app.route("/empleados/<int:emp_id>/password/restablecer", methods=["POST"])
@seg.solo_rrhh
def restablecer_password(emp_id):
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    empleado = cargar_empleado(cursor, emp_id)
    cursor.execute("SELECT id FROM usuarios WHERE empleado_id = %s", (emp_id,))
    if cursor.fetchone() is None:
        crear_cuenta(cursor, emp_id)
    else:
        cursor.execute("UPDATE usuarios SET password_hash = %s, debe_cambiar = 1, intentos_fallidos = 0, "
                       "bloqueado_hasta = NULL WHERE empleado_id = %s",
                       (seg.hash_password(seg.PASSWORD_INICIAL), emp_id))
    registrar_cambios(cursor, emp_id, "cuenta", [("Contraseña", "", "Restablecida por RRHH")])
    conexion.commit()
    cursor.close()
    conexion.close()
    flash("La contraseña de %s volvió a %s y deberá cambiarla al ingresar." % (
        empleado["codigo"], seg.PASSWORD_INICIAL), "ok")
    return redirect("/empleados/%d" % emp_id)


# Eliminar perfil
@app.route("/empleados/eliminar/<int:emp_id>", methods=["POST"])
@seg.solo_rrhh
def eliminar(emp_id):
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    empleado = cargar_empleado(cursor, emp_id)
    cursor.execute("SELECT COUNT(*) AS n FROM archivos WHERE empleado_id = %s", (emp_id,))
    if cursor.fetchone()["n"] > 0:
        cursor.close()
        conexion.close()
        flash("%s no se puede eliminar porque tiene archivos subidos. Cambia su estado a Inactivo si ya no "
              "trabaja en el hospital." % empleado["codigo"], "error")
        return redirect("/empleados")
    # El historial y la cuenta se borran solos (ON DELETE CASCADE)
    cursor.execute("DELETE FROM expediente WHERE empleado_id = %s", (emp_id,))
    cursor.execute("DELETE FROM empleados WHERE id = %s", (emp_id,))
    conexion.commit()
    cursor.close()
    conexion.close()
    flash("Se eliminó el perfil %s." % empleado["codigo"], "ok")
    return redirect("/empleados")


# Expediente completo en un solo PDF
def volcar_archivo(archivo_id, ruta):
    """Escribe en disco un archivo guardado en la base, pedazo por pedazo."""
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("SELECT contenido FROM archivos WHERE id = %s", (archivo_id,))
    with open(ruta, "wb") as salida:
        salida.write(bytes(cursor.fetchone()[0]))
        orden = 1
        while True:
            cursor.execute("SELECT contenido FROM archivo_partes WHERE archivo_id = %s AND orden = %s",
                           (archivo_id, orden))
            parte = cursor.fetchone()
            if parte is None:
                break
            salida.write(bytes(parte[0]))
            orden = orden + 1
    cursor.close()
    conexion.close()


@app.route("/empleados/<int:emp_id>/expediente.pdf")
@seg.solo_rrhh
def descargar_expediente(emp_id):
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    empleado = cargar_empleado(cursor, emp_id)
    cursor.execute("SELECT COUNT(*) AS n FROM documentos")
    total = cursor.fetchone()["n"]
    # La versión más reciente de cada documento
    cursor.execute("""
        SELECT a.id, a.documento_id, d.nombre AS documento, a.version, a.nombre_original
        FROM archivos a JOIN documentos d ON d.id = a.documento_id
        WHERE a.empleado_id = %s
          AND a.version = (SELECT MAX(a2.version) FROM archivos a2
                           WHERE a2.empleado_id = a.empleado_id AND a2.documento_id = a.documento_id)
        ORDER BY d.id
    """, (emp_id,))
    archivos = cursor.fetchall()
    if total == 0 or len(archivos) < total:
        cursor.close()
        conexion.close()
        flash("El expediente aún no está completo: faltan %d documento(s)." % (total - len(archivos)), "error")
        return redirect("/empleados/%d?pestana=documentos" % emp_id)

    carpeta = tempfile.mkdtemp(prefix="hdd_expediente_")
    try:
        for archivo in archivos:
            archivo["ruta"] = os.path.join(carpeta, "doc_%d.pdf" % archivo["id"])
            volcar_archivo(archivo["id"], archivo["ruta"])
        destino = os.path.join(carpeta, "expediente.pdf")
        construir_expediente(empleado, archivos, destino, session.get("correo", "RRHH"),
                             logo=os.path.join(CARPETA, "static", "logo.png"))
    except ErrorExpediente as e:
        shutil.rmtree(carpeta, ignore_errors=True)
        cursor.close()
        conexion.close()
        flash(str(e), "error")
        return redirect("/empleados/%d?pestana=documentos" % emp_id)
    except Exception:
        shutil.rmtree(carpeta, ignore_errors=True)
        cursor.close()
        conexion.close()
        raise

    registrar_cambios(cursor, emp_id, "expediente", [("Expediente consolidado", "", "Generado en PDF por RRHH")])
    conexion.commit()
    cursor.close()
    conexion.close()

    def entregar():
        try:
            with open(destino, "rb") as f:
                while True:
                    bloque = f.read(TAMANO_PARTE)
                    if not bloque:
                        break
                    yield bloque
        finally:
            shutil.rmtree(carpeta, ignore_errors=True)

    respuesta = Response(entregar(), mimetype="application/pdf")
    respuesta.headers["Content-Disposition"] = "attachment; filename*=UTF-8''" + quote(
        "Expediente_%s.pdf" % empleado["codigo"])
    respuesta.headers["Content-Length"] = str(os.path.getsize(destino))
    return respuesta


# Resumen
@app.route("/resumen")
@seg.solo_rrhh
def resumen():
    filas = obtener_empleados()
    completos = 0
    con_vencidos = 0
    en_proceso = 0
    sin_archivos = 0
    docs_subidos = 0
    docs_requeridos = 0
    detalle = []
    for fila in filas:
        docs_subidos = docs_subidos + fila["con_archivo"]
        docs_requeridos = docs_requeridos + fila["total"]
        if fila["total"] > 0 and fila["con_archivo"] == fila["total"] and fila["vencidos"] == 0:
            completos = completos + 1
            clase, estado = "completo", "Completo (todos subidos y vigentes)"
        elif fila["vencidos"] > 0:
            con_vencidos = con_vencidos + 1
            clase, estado = "vencidos", "Con documentos vencidos"
        elif fila["con_archivo"] > 0:
            en_proceso = en_proceso + 1
            clase, estado = "proceso", "Incompleto (en proceso)"
        else:
            sin_archivos = sin_archivos + 1
            clase, estado = "vacio", "Incompleto (sin archivos)"
        detalle.append({"datos": fila, "estado": estado, "clase": clase})
    return render_template("resumen.html", detalle=detalle, total=len(filas),
                           completos=completos, con_vencidos=con_vencidos,
                           en_proceso=en_proceso, sin_archivos=sin_archivos,
                           docs_subidos=docs_subidos, docs_requeridos=docs_requeridos)


# ====================================================================
#   PORTAL DEL EMPLEADO
# ====================================================================
@app.route("/mi/expediente")
@seg.solo_empleado
def mi_expediente():
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    empleado = cargar_empleado(cursor, session["empleado_id"])
    grupos, checklist, pendientes, r = datos_documentos(cursor, empleado["id"])
    cursor.close()
    conexion.close()
    return render_template("mi_expediente.html", empleado=empleado, grupos=grupos, pendientes=pendientes,
                           r=r, completo=perfil_completo(empleado))


@app.route("/mi/perfil", methods=["GET", "POST"])
@seg.solo_empleado
def mi_perfil():
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    empleado = cargar_empleado(cursor, session["empleado_id"])
    datos = {c: texto(empleado[c]) for c in CAMPOS_EMPLEADO}
    error = ""
    if request.method == "POST":
        # Solo se leen los tres campos permitidos: cualquier otro dato enviado se ignora
        for campo in CAMPOS_EMPLEADO:
            datos[campo] = request.form.get(campo, "").strip()
        error = validar_personales(datos, obligatorios=True)
        if not error:
            cambios = diferencias(empleado, datos, CAMPOS_EMPLEADO)
            if cambios:
                cursor.execute(
                    "UPDATE empleados SET fecha_nacimiento = %s, estado_civil = %s, direccion = %s WHERE id = %s",
                    (datos["fecha_nacimiento"], datos["estado_civil"], datos["direccion"], empleado["id"]))
                registrar_cambios(cursor, empleado["id"], "perfil", cambios)
                conexion.commit()
                flash("Tus datos se actualizaron.", "ok")
            else:
                flash("No hubo cambios que guardar.", "ok")
            cursor.close()
            conexion.close()
            return redirect("/mi/expediente")
    cursor.close()
    conexion.close()
    return render_template("mi_perfil.html", empleado=empleado, datos=datos, error=error,
                           estados_civiles=ESTADOS_CIVILES)


@app.route("/mi/historial")
@seg.solo_empleado
def mi_historial():
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    empleado = cargar_empleado(cursor, session["empleado_id"])
    historial = leer_historial(cursor, empleado["id"])
    cursor.close()
    conexion.close()
    return render_template("mi_historial.html", empleado=empleado, historial=historial)


# Subir un archivo (el empleado sube sus propios documentos; cada subida es una versión nueva)
@app.route("/mi/subir", methods=["GET", "POST"])
@seg.solo_empleado
def subir():
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    empleado = cargar_empleado(cursor, session["empleado_id"])
    emp_id = empleado["id"]
    cursor.execute("SELECT id, nombre, requiere_vencimiento FROM documentos ORDER BY id")
    documentos = cursor.fetchall()

    error = ""
    datos = {"documento_id": request.args.get("documento", ""), "fecha_vencimiento": ""}
    if request.method == "POST":
        datos["documento_id"] = request.form.get("documento_id", "").strip()
        datos["fecha_vencimiento"] = request.form.get("fecha_vencimiento", "").strip()

        archivo = request.files.get("archivo")
        nombre = ""
        tamano = 0
        firma = b""
        if archivo is not None and archivo.filename:
            # Solo el nombre, sin carpetas
            nombre = archivo.filename.replace("\\", "/").split("/")[-1].strip()[:255]
            # El tamaño se obtiene moviéndose al final del flujo, sin cargar el archivo en memoria
            archivo.stream.seek(0, os.SEEK_END)
            tamano = archivo.stream.tell()
            archivo.stream.seek(0)
            firma = archivo.stream.read(5)
            archivo.stream.seek(0)
        extension = os.path.splitext(nombre)[1].lower()

        documento = None
        for d in documentos:
            if str(d["id"]) == datos["documento_id"]:
                documento = d

        vencimiento_valido = datos["fecha_vencimiento"] == "" or fecha_valida(datos["fecha_vencimiento"])

        if documento is None:
            error = "Selecciona el tipo de documento."
        elif nombre == "":
            error = "Selecciona un archivo."
        elif extension not in EXTENSIONES_PERMITIDAS:
            error = "Solo se permiten archivos PDF."
        elif tamano == 0:
            error = "El archivo está vacío."
        elif tamano > MAX_BYTES:
            error = "El archivo supera el tamaño máximo de %s." % formato_tamano(MAX_BYTES)
        elif firma != b"%PDF-":
            error = "El archivo no es un PDF válido. Verifica que no esté dañado."
        elif documento["requiere_vencimiento"] and datos["fecha_vencimiento"] == "":
            error = "Este documento requiere fecha de vencimiento."
        elif not vencimiento_valido:
            error = "La fecha de vencimiento no es válida."
        else:
            cursor.execute(
                "SELECT MAX(version) AS ultima FROM archivos WHERE empleado_id = %s AND documento_id = %s",
                (emp_id, documento["id"]))
            version = (cursor.fetchone()["ultima"] or 0) + 1
            # El primer pedazo va en la fila del archivo; el resto, en archivo_partes
            primera = archivo.stream.read(TAMANO_PARTE)
            cursor.execute(
                "INSERT INTO archivos (empleado_id, documento_id, version, nombre_original, tamano, "
                "contenido, fecha_vencimiento) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (emp_id, documento["id"], version, nombre, tamano, primera,
                 datos["fecha_vencimiento"] or None))
            archivo_id = cursor.lastrowid
            orden = 1
            while True:
                pedazo = archivo.stream.read(TAMANO_PARTE)
                if not pedazo:
                    break
                cursor.execute(
                    "INSERT INTO archivo_partes (archivo_id, orden, contenido) VALUES (%s, %s, %s)",
                    (archivo_id, orden, pedazo))
                orden = orden + 1
            cursor.execute(
                "UPDATE expediente SET entregado = 1 WHERE empleado_id = %s AND documento_id = %s",
                (emp_id, documento["id"]))
            anterior = ("v%d" % (version - 1)) if version > 1 else ""
            registrar_cambios(cursor, emp_id, "documento", [(
                documento["nombre"], anterior, "v%d · %s (%s)" % (version, nombre, formato_tamano(tamano)))])
            # Todo o nada: si algo falla antes de este commit no queda un archivo a medias
            conexion.commit()
            cursor.close()
            conexion.close()
            flash("%s se guardó como versión %d." % (nombre, version), "ok")
            return redirect("/mi/expediente")
    cursor.close()
    conexion.close()
    return render_template("subir.html", empleado=empleado, documentos=documentos, datos=datos,
                           error=error, limite_texto=formato_tamano(MAX_BYTES), max_bytes=MAX_BYTES)


# ====================================================================
#   ARCHIVOS (RRHH y dueño del archivo)
# ====================================================================
def enviar_archivo(archivo_id, en_linea):
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT empleado_id, nombre_original, tamano, contenido FROM archivos WHERE id = %s",
                   (archivo_id,))
    fila = cursor.fetchone()
    if fila is None:
        cursor.close()
        conexion.close()
        abort(404)
    # RRHH ve todo; el empleado solo lo suyo
    if session.get("rol") != "rrhh" and fila["empleado_id"] != session.get("empleado_id"):
        cursor.close()
        conexion.close()
        abort(403)
    cursor.execute("SELECT COUNT(*) AS n FROM archivo_partes WHERE archivo_id = %s", (archivo_id,))
    hay_partes = cursor.fetchone()["n"] > 0
    cursor.close()
    conexion.close()

    primera = bytes(fila["contenido"])
    nombre = fila["nombre_original"]
    es_pdf = primera[:5] == b"%PDF-"
    if en_linea and not es_pdf:
        abort(415)

    def leer_partes():
        # Se entrega pedazo por pedazo para no cargar un archivo de 1 GB en memoria
        yield primera
        con = conectar()
        cur = con.cursor()
        try:
            orden = 1
            while True:
                cur.execute("SELECT contenido FROM archivo_partes WHERE archivo_id = %s AND orden = %s",
                            (archivo_id, orden))
                parte = cur.fetchone()
                if parte is None:
                    break
                yield bytes(parte[0])
                orden = orden + 1
        finally:
            cur.close()
            con.close()

    cuerpo = leer_partes() if hay_partes else primera
    respuesta = Response(cuerpo, mimetype="application/pdf" if es_pdf else "application/octet-stream")
    disposicion = "inline" if en_linea else "attachment"
    respuesta.headers["Content-Disposition"] = "%s; filename*=UTF-8''%s" % (disposicion, quote(nombre))
    respuesta.headers["Content-Length"] = str(fila["tamano"])
    return respuesta


@app.route("/archivos/<int:archivo_id>/descargar")
def descargar(archivo_id):
    return enviar_archivo(archivo_id, en_linea=False)


@app.route("/archivos/<int:archivo_id>/ver")
def ver_archivo(archivo_id):
    return enviar_archivo(archivo_id, en_linea=True)


# ---------- Errores ----------
@app.errorhandler(mysql.connector.Error)
def error_mysql(e):
    print("Error de MySQL:", e)
    return render_template("error.html", titulo="No se pudo usar la base de datos",
                           mensaje="Verifica que MySQL esté iniciado en XAMPP y que importaste "
                                   "crear_bd.sql (o migracion_v3.sql) en phpMyAdmin.",
                           detalle=str(e)), 500


@app.errorhandler(403)
def sin_permiso(e):
    return render_template("error.html", titulo="Acceso restringido",
                           mensaje="Tu cuenta no tiene permiso para ver esta página.", detalle=""), 403


@app.errorhandler(404)
def no_encontrado(e):
    return render_template("error.html", titulo="Página no encontrada",
                           mensaje="El registro o la página que buscas no existe.", detalle=""), 404


@app.errorhandler(413)
def archivo_demasiado_grande(e):
    return render_template("error.html", titulo="Archivo demasiado grande",
                           mensaje="El archivo supera el máximo de %s por documento." % formato_tamano(MAX_BYTES),
                           detalle=""), 413


@app.errorhandler(415)
def sin_vista_previa(e):
    return render_template("error.html", titulo="Vista previa no disponible",
                           mensaje="Este archivo no es un PDF, así que no se puede previsualizar. "
                                   "Puedes descargarlo.", detalle=""), 415


if __name__ == "__main__":
    app.run(debug=True)
