# Expedientes Digitales · Hospital de Diagnóstico

Sistema web interno para la gestión del expediente documental del personal del Hospital de Diagnóstico. Cuenta con **dos portales**: Recursos Humanos (RRHH) administra y revisa los perfiles, y cada empleado completa sus datos y sube sus propios documentos. Todo se guarda en la base de datos, con historial de versiones de archivos y bitácora de cambios de cada perfil.

![Python](https://img.shields.io/badge/Python-3.10%2B-1d4796) ![Flask](https://img.shields.io/badge/Flask-3.x-0f2a5f) ![MySQL](https://img.shields.io/badge/MySQL%20%2F%20MariaDB-XAMPP-6f82a0)

---

## Contenido
1. [Resumen ejecutivo](#resumen-ejecutivo)
2. [Roles y accesos](#roles-y-accesos)
3. [Funcionalidades](#funcionalidades)
4. [Arquitectura y tecnologías](#arquitectura-y-tecnologías)
5. [Instalación y ejecución](#instalación-y-ejecución)
6. [Acceso con Microsoft 365 (RRHH)](#acceso-con-microsoft-365-rrhh)
7. [Actualizar una base de datos existente](#actualizar-una-base-de-datos-existente)
8. [Estructura del proyecto](#estructura-del-proyecto)
9. [Modelo de datos](#modelo-de-datos)
10. [Gestión de archivos](#gestión-de-archivos)
11. [Historial de cambios](#historial-de-cambios)
12. [Reglas de negocio y seguridad](#reglas-de-negocio-y-seguridad)
13. [Rutas del sistema](#rutas-del-sistema)
14. [Equipo y responsabilidades](#equipo-y-responsabilidades)

---

## Resumen ejecutivo
El área de Talento Humano necesita saber, en cualquier momento, qué empleados tienen su expediente completo, cuáles tienen documentos vencidos y cuáles no han entregado nada. Este sistema responde esas preguntas desde un panel único, con una interfaz alineada a la identidad visual del hospital.

| Indicador | Detalle |
|---|---|
| Documentos por expediente | 12 tipos de documento por empleado |
| Tamaño máximo por archivo | 1 GB, almacenado como BLOB en MySQL |
| Formato admitido | Solo PDF |
| Acceso | Empleados con código y contraseña; RRHH con cuenta de Microsoft 365 |
| Códigos de empleado | Automáticos y únicos (`HDD-0001`, `HDD-0002`...) |
| Sucursales | Escalón, Santa Elena y Colonia Médica |

## Roles y accesos

| | Recursos Humanos | Empleado |
|---|---|---|
| **Cómo ingresa** | Botón *Iniciar sesión con Microsoft* con su cuenta `@keyinstitute.edu.sv` | Código de empleado (`HDD-0001`) y contraseña |
| **Ve** | Todos los perfiles, documentos e historiales | Únicamente su propio expediente |
| **Edita** | Todos los datos del perfil, incluidos los personales, para corregir errores | Solo fecha de nacimiento, estado civil y dirección |
| **Documentos** | **Elige cuáles se le solicitan a cada empleado**; los revisa, previsualiza y descarga. **No sube ni reemplaza archivos** | Ve y sube únicamente los documentos que RRHH le solicitó (cada subida es una versión nueva) |
| **Expediente completo** | Descarga un solo PDF con los documentos solicitados cuando el empleado terminó de subirlos | No aplica |
| **Historial** | Ve el historial de cualquier perfil | Ve únicamente el de su perfil |

Contraseña inicial de los empleados: `123456789`. El sistema obliga a cambiarla en el primer ingreso (mínimo 8 caracteres, con letras y números). Tras 5 intentos fallidos, la cuenta se bloquea 10 minutos. Un empleado con estado *Inactivo* no puede ingresar.

## Funcionalidades

**Gestión de personal**
- Registro de empleados con código **generado automáticamente**; el código nunca se repite, aunque el perfil se elimine de la base de datos.
- Menús desplegables para puesto, área, sucursal y estado laboral (Activo, Inactivo, Licencia médica, Vacaciones).
- Edición del perfil por RRHH. El código es inmutable y cada cambio queda registrado.
- Datos personales (fecha de nacimiento, estado civil, dirección) que completa el propio empleado.
- RRHH puede restablecer la contraseña de un empleado a la inicial.
- Eliminación **restrictiva**: un perfil con archivos o documentos asociados no puede borrarse desde el sistema.

**Gestión documental**
- **Documentos solicitados por empleado**: RRHH elige, desde un desplegable con casillas que siempre muestra los 12 documentos del catálogo, cuáles debe entregar cada perfil (por ejemplo, 8 de 12 para un puesto operativo). Los demás no aparecen en el perfil del empleado, ni en su checklist, ni en su formulario de subida, y el servidor rechaza cualquier intento de subirlos. Se define al registrar al empleado y se puede ajustar después; quitar un documento no borra sus archivos, solo deja de pedirse y de contar.
- Portal del empleado con su avance, sus documentos pendientes y botón de subida con **arrastrar y soltar**, validación inmediata y barra de progreso.
- **Checklist automático**: el documento se marca como entregado en cuanto el empleado lo sube; nadie lo marca a mano.
- **Vista previa** de los PDF en una ventana flotante, sin descargarlos.
- **Expediente consolidado**: RRHH descarga un único PDF con portada, índice, marcadores y la versión más reciente de cada documento (se habilita cuando están todos los solicitados al empleado).
- **Control de versiones**: subir un documento nunca reemplaza al anterior; se conserva todo el historial.
- Estado automático por documento: *Vigente*, *Vencido* o *Versión anterior*, con aviso de días para el vencimiento.
- Descarga de cualquier versión, con permisos: RRHH accede a todas y cada empleado solo a las suyas.

**Analítica y control**
- Panel de indicadores con expedientes completos, con vencidos y documentos subidos.
- Resumen que clasifica cada expediente: *Completo*, *Con documentos vencidos*, *Incompleto en proceso* e *Incompleto sin archivos*.

**Continuidad operativa**
- **Historial de cambios** por perfil: quién cambió qué, cuándo, y el valor anterior y el nuevo.
- Si Apache o MySQL se detienen en el Panel de Control de XAMPP, el sistema deja de operar y muestra una pantalla con el estado de cada servicio, en lugar de fallar de forma confusa.

## Arquitectura y tecnologías

| Capa | Tecnología | Responsabilidad |
|---|---|---|
| Presentación | HTML, plantillas Jinja2, CSS, JavaScript | Interfaz con identidad del hospital, formularios y subida con arrastre |
| Aplicación | Python y Flask | Rutas, validaciones, roles y reglas de negocio |
| Seguridad | `werkzeug` (hash de contraseñas), OAuth 2.0 / OpenID Connect con Microsoft Entra ID | Autenticación de empleados y de RRHH |
| Documentos | `pypdf` y `reportlab` | Unión de PDF y portada del expediente consolidado |
| Datos | MySQL / MariaDB (XAMPP) vía `mysql-connector-python` | Persistencia relacional y almacenamiento de archivos |

Decisiones de diseño relevantes:
- **Consultas parametrizadas** (`%s`) en todo el acceso a datos, sin concatenar texto del usuario en el SQL.
- **Archivos por fragmentos**: cada archivo se divide en bloques de 256 KB. Ningún paquete supera el límite por defecto de MySQL (`max_allowed_packet`), y la descarga se entrega en flujo sin cargar el archivo completo en memoria.
- **Subida transaccional**: el archivo se guarda con un único `commit`; si algo falla, no queda información a medias.
- **Contraseñas con hash**: nunca se guardan en texto plano.
- **Integridad referencial** con llaves foráneas y `ON DELETE CASCADE` en las tablas dependientes.

## Instalación y ejecución

**Requisitos:** Python 3.10 o superior y XAMPP con Apache y MySQL.

1. Abrir el Panel de Control de XAMPP e **iniciar Apache y MySQL**.
2. Entrar a `http://localhost/phpmyadmin/`, pestaña **Importar**, elegir `crear_bd.sql` y pulsar **Continuar**. El script crea la base `hospital_hdd` y carga datos de ejemplo.
   > Atención: el script elimina y recrea las tablas. Ejecutarlo de nuevo borra los datos existentes. Si ya tienes datos, usa la [migración](#actualizar-una-base-de-datos-existente).
3. (Recomendado) Crear y activar un entorno virtual:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
4. Instalar las dependencias:
   ```
   python -m pip install -r requirements.txt
   ```
5. Crear el archivo de configuración: copiar `.env.ejemplo` como `.env` y completar los valores (ver la sección de Microsoft 365). El archivo `.env` **nunca se sube a GitHub**.
6. Ejecutar la aplicación desde la carpeta del proyecto:
   ```
   python app.py
   ```
7. Abrir **`http://localhost:5000`** (no `127.0.0.1`: Microsoft compara la dirección letra por letra; el sistema redirige de una a otra automáticamente).

Conexión a la base de datos: usuario `root` sin contraseña (valores por defecto de XAMPP), definidos en la función `conectar()` de `app.py`.

**Primer ingreso de prueba (empleado):** código `HDD-0001`, contraseña `123456789`.

**Solución de problemas**

| Mensaje | Causa probable | Solución |
|---|---|---|
| El sistema no está disponible | Apache o MySQL detenidos | Iniciarlos en XAMPP y pulsar *Volver a comprobar* |
| `Table '...' doesn't exist` | Base de datos con esquema anterior | Volver a importar `crear_bd.sql` |
| `No module named 'flask'` (o `pypdf`, `requests`...) | Dependencias sin instalar | Ejecutar `python -m pip install -r requirements.txt` |
| *El acceso con Microsoft aún no está configurado* | Falta el archivo `.env` o alguno de sus valores | Completar `.env` y reiniciar la aplicación |
| Microsoft muestra un error de *redirect URI* | Se entró por `127.0.0.1` o el URI registrado no coincide | Entrar por `http://localhost:5000` y revisar el URI en Entra |

## Acceso con Microsoft 365 (RRHH)

RRHH ingresa con su cuenta institucional. La contraseña de Microsoft nunca pasa por este sistema: Microsoft devuelve la identidad ya verificada y la aplicación comprueba que la cuenta pertenezca al directorio autorizado y termine en `@keyinstitute.edu.sv` (valor configurable en `RRHH_DOMINIO`). Cualquier cuenta de ese dominio entra como RRHH.

**Registrar la aplicación (una sola vez, es gratuito):**
1. Entrar a [entra.microsoft.com](https://entra.microsoft.com) → *Registros de aplicaciones* → *Nuevo registro*.
2. Nombre: `Expedientes Digitales HDD`. Tipo de cuenta: *Solo inquilino único*.
3. URI de redirección, plataforma **Web**: `http://localhost:5000/auth/microsoft/callback`.
4. En *Información general* copiar el **Id. de aplicación (cliente)** y el **Id. de directorio (inquilino)**.
5. En *Certificados y secretos* → *Nuevo secreto de cliente*, copiar la columna **Valor** (solo se muestra una vez).

**Archivo `.env`** (en la carpeta del proyecto, junto a `app.py`):
```
HDD_SECRET_KEY=un-texto-largo-y-aleatorio
MS_CLIENT_ID=<Id. de aplicación (cliente)>
MS_TENANT_ID=<Id. de directorio (inquilino)>
MS_CLIENT_SECRET=<Valor del secreto>
MS_REDIRECT_URI=http://localhost:5000/auth/microsoft/callback
RRHH_DOMINIO=keyinstitute.edu.sv
```
El secreto equivale a una contraseña: no se comparte ni se sube a GitHub (`.gitignore` ya excluye `.env`). Si se expone, se elimina en Entra y se crea otro. Los secretos tienen fecha de caducidad; al vencer hay que generar uno nuevo y actualizar `.env`.

## Actualizar una base de datos existente
Si ya tienes datos de una versión anterior y no quieres perderlos, en phpMyAdmin selecciona la base `hospital_hdd` y ejecuta `migracion_v3.sql` (pestaña *Importar*). Agrega las columnas personales a `empleados`, crea las tablas `usuarios` e `historial_cambios` y sincroniza el checklist con los archivos ya subidos. Está pensada para MariaDB (XAMPP) y se ejecuta una sola vez. Las cuentas de los empleados existentes se crean solas en su primer ingreso.

Si ya aplicaste la v3, ejecuta además `migracion_v4.sql` para activar los **documentos solicitados por empleado**. No modifica la estructura: deja a todos los empleados existentes con los 12 documentos solicitados, para que RRHH ajuste perfil por perfil. Se puede ejecutar más de una vez sin duplicar nada.

## Estructura del proyecto
```
.
├── app.py               Rutas de Flask (portal RRHH y portal del empleado), validaciones y lógica
├── seguridad.py         Contraseñas, sesiones, CSRF, roles y acceso con Microsoft
├── expediente_pdf.py    Construcción del expediente consolidado en PDF
├── crear_bd.sql         Esquema de la base de datos y datos de ejemplo (instalación nueva)
├── migracion_v3.sql     Actualiza una base existente sin perder datos
├── migracion_v4.sql     Documentos solicitados por empleado (sobre la v3)
├── .env.ejemplo         Plantilla de configuración (copiar como .env, que no se sube a GitHub)
├── requirements.txt     Dependencias: flask, mysql-connector-python, requests, pypdf, reportlab
├── README.md
├── templates/
│   ├── base.html            Estructura común: menú según el rol, logo y mensajes
│   ├── login.html           Inicio de sesión (empleado / RRHH con Microsoft)
│   ├── cambiar_password.html
│   ├── empleados.html       Panel de RRHH: indicadores y listado
│   ├── perfil_rrhh.html     Perfil para RRHH: datos, documentos e historial
│   ├── nuevo.html           Registro de empleados
│   ├── editar.html          Edición de perfil por RRHH
│   ├── resumen.html         Clasificación de expedientes
│   ├── mi_expediente.html   Portal del empleado: avance y documentos
│   ├── mi_perfil.html       Datos personales que puede editar el empleado
│   ├── mi_historial.html    Historial de su perfil
│   ├── subir.html           Subida de documentos (multipart/form-data)
│   ├── _documentos.html     Tarjetas de documentos y versiones (parcial)
│   ├── _historial.html      Tabla de historial (parcial)
│   ├── _vista.html          Ventana de vista previa de PDF (parcial)
│   ├── servicios.html       Pantalla de servicios detenidos
│   └── error.html           Errores controlados
└── static/
    ├── style.css        Hoja de estilos única del sistema
    ├── subir.js         Arrastrar y soltar, validación y progreso
    ├── solicitados.js   Desplegable de documentos solicitados (contador y marcar todos)
    ├── vista.js         Ventana de vista previa de PDF
    └── logo.png         Logotipo del hospital
```

## Modelo de datos
Base de datos `hospital_hdd`.

| Tabla | Propósito | Campos principales |
|---|---|---|
| `secuencia_codigos` | Contador de códigos de empleado; solo avanza | `nombre` (PK), `ultimo` |
| `empleados` | Perfil del colaborador | `id` (PK), `codigo` (único), `nombre`, `puesto`, `area`, `sucursal`, `estado`, `fecha_ingreso`, `fecha_nacimiento`, `estado_civil`, `direccion` |
| `usuarios` | Cuenta de acceso de cada empleado (RRHH entra con Microsoft y no tiene fila) | `id` (PK), `empleado_id` (FK, único), `password_hash`, `debe_cambiar`, `intentos_fallidos`, `bloqueado_hasta`, `ultimo_acceso` |
| `historial_cambios` | Bitácora de cambios por perfil (solo se agregan filas) | `id` (PK), `empleado_id` (FK), `lote`, `actor`, `rol_actor`, `tipo`, `campo`, `valor_anterior`, `valor_nuevo`, `fecha` |
| `documentos` | Catálogo de documentos requeridos | `id` (PK), `nombre`, `requiere_vencimiento` |
| `expediente` | Documentos que RRHH le solicita a cada empleado: una fila = un documento solicitado (`entregado` ya no se usa; el avance sale de los archivos) | `empleado_id` (PK, FK), `documento_id` (PK, FK), `entregado` |
| `archivos` | Cada versión subida | `id` (PK), `empleado_id` (FK), `documento_id` (FK), `version`, `nombre_original`, `tamano`, `contenido` (LONGBLOB), `fecha_vencimiento`, `fecha_subida` |
| `archivo_partes` | Resto de cada archivo en bloques de 256 KB | `archivo_id` (PK, FK), `orden` (PK), `contenido` (LONGBLOB) |

Relaciones e integridad:
- `expediente`, `usuarios`, `historial_cambios`, `archivos` y `archivo_partes` dependen de su tabla padre con `ON DELETE CASCADE`.
- `UNIQUE (empleado_id, documento_id, version)` impide duplicar una versión.
- `empleados.codigo` es único.

## Gestión de archivos
- Solo el **empleado** sube archivos; RRHH únicamente los revisa.
- El formulario usa `method="POST"` y `enctype="multipart/form-data"`; Flask recibe el archivo con `request.files`.
- **Validaciones:** documento seleccionado, archivo presente, extensión `.pdf`, contenido realmente PDF (firma `%PDF-`, no solo la extensión), archivo no vacío, tamaño máximo de 1 GB, fecha de vencimiento obligatoria para el DUI y fecha válida. Se verifican en el navegador y de nuevo en el servidor.
- **Versionado:** la versión siguiente se calcula con `SELECT MAX(version)`; la primera es 1.
- **Almacenamiento:** el primer bloque de 256 KB se guarda en `archivos.contenido` y el resto, en `archivo_partes`.
- **Estados** (decididos con `if/elif/else`):
  - *Versión anterior*: existe otra más reciente del mismo documento.
  - *Vencido*: es la versión más reciente y su fecha de vencimiento ya pasó.
  - *Vigente*: es la versión más reciente y no está vencida.
- **Vista previa:** `/archivos/<id>/ver` sirve el PDF en línea dentro de una ventana flotante. Solo se previsualiza lo que realmente es PDF.
- **Expediente consolidado:** se arma con la versión más reciente de cada uno de los 12 documentos, precedida de una portada con los datos del empleado y un índice con número de página; incluye marcadores. Si un PDF está dañado o protegido con contraseña, el sistema indica cuál.
- Los archivos Word que se hayan subido antes de esta versión se conservan y se pueden descargar, pero no se previsualizan ni se incluyen en el expediente consolidado.
- Un archivo de 1 GB requiere tiempo de subida y espacio libre en el disco donde XAMPP guarda sus datos.
- Se recomienda trabajar solo con documentos de prueba, nunca con documentos personales reales.

## Historial de cambios
Cada vez que cambia algo en un perfil queda constancia: **quién** lo hizo (correo de RRHH o código del empleado), **cuándo**, **qué campo** y el **valor anterior y el nuevo**. Se registran:
- Cambios en el perfil, hechos por RRHH o por el empleado. Solo se guardan los campos que realmente cambiaron.
- Cada documento subido (con su versión).
- Cambios y restablecimientos de contraseña, sin guardar nunca la contraseña.
- La generación del expediente consolidado.

El registro se escribe en la misma transacción que el cambio: si el cambio falla, tampoco queda registro. No existe ninguna pantalla para editar o borrar el historial. RRHH lo consulta en la pestaña *Historial de cambios* del perfil, y cada empleado ve solo el suyo.

## Reglas de negocio y seguridad
- El código de empleado lo asigna el servidor; cualquier valor enviado desde el formulario se ignora.
- Los menús desplegables se validan también en el servidor: un valor fuera de las listas se rechaza.
- Un empleado solo puede ver y subir los documentos que RRHH le solicitó, y el servidor lo valida; un perfil siempre debe tener al menos un documento solicitado.
- Un perfil solo puede eliminarse si no tiene archivos subidos; en caso contrario, se recomienda cambiar su estado a *Inactivo*.
- Los nombres de archivo se limpian y nunca se usan como ruta en disco, porque el contenido vive en la base de datos.
- Todas las consultas son parametrizadas.
- Control de acceso en dos capas: un filtro general que exige sesión y un decorador por rol en cada ruta. Un empleado no puede abrir páginas de RRHH ni archivos de otro empleado.
- Todos los formularios POST llevan token CSRF.
- Las contraseñas se guardan con hash; bloqueo temporal tras 5 intentos fallidos; cambio obligatorio de la contraseña inicial.
- Los datos que un empleado envíe fuera de los tres campos permitidos se ignoran en el servidor.
- Las respuestas no se guardan en caché del navegador, para que al cerrar sesión no se pueda volver atrás y ver datos.
- El secreto de Microsoft y la clave de sesión viven en `.env`, fuera del repositorio.

## Rutas del sistema

**Públicas**

| Ruta | Método | Función |
|---|---|---|
| `/login` | GET, POST | Inicio de sesión de empleados y acceso a RRHH |
| `/auth/microsoft` y `/auth/microsoft/callback` | GET | Inicio de sesión de RRHH con Microsoft 365 |

**Recursos Humanos**

| Ruta | Método | Función |
|---|---|---|
| `/empleados` | GET | Panel con indicadores y listado de empleados |
| `/empleados/nuevo` | GET, POST | Registro con código y cuenta automáticos, y selección de documentos solicitados |
| `/empleados/<id>` | GET | Perfil: datos, documentos (checklist) e historial |
| `/empleados/editar/<id>` | GET, POST | Edición de perfil |
| `/empleados/<id>/documentos-solicitados` | POST | Define qué documentos se le solicitan al empleado |
| `/empleados/<id>/password/restablecer` | POST | Devuelve la contraseña a la inicial |
| `/empleados/<id>/expediente.pdf` | GET | Expediente completo en un solo PDF |
| `/empleados/eliminar/<id>` | POST | Eliminación restrictiva |
| `/resumen` | GET | Clasificación de expedientes y contadores |

**Empleado**

| Ruta | Método | Función |
|---|---|---|
| `/mi/expediente` | GET | Avance, documentos y pendientes |
| `/mi/perfil` | GET, POST | Edición de fecha de nacimiento, estado civil y dirección |
| `/mi/historial` | GET | Historial de su perfil |
| `/mi/subir` | GET, POST | Subida de un documento PDF (nueva versión) |
| `/cuenta/password` | GET, POST | Cambio de contraseña |

**Compartidas (RRHH y dueño del archivo)**

| Ruta | Método | Función |
|---|---|---|
| `/archivos/<id>/ver` | GET | Vista previa en línea del PDF |
| `/archivos/<id>/descargar` | GET | Descarga de una versión |
| `/logout` | POST | Cerrar sesión |

## Equipo y responsabilidades

| Integrante | Rol | Responsabilidades |
|---|---|---|
| **Herberth Barrera** | Tech Lead | Lidera la integración técnica y la armonización del código fuente (`app.py`). Diseña y mantiene la interfaz gráfica del sistema en HTML (`templates/`), garantizando coherencia visual y experiencia de usuario. |
| **Hector Calderon** | Developer | Responsable del manejo de la información y la conexión con la base de datos: consultas, acceso a datos y persistencia. Mantiene los recursos de la carpeta `static/`. |
| **Camila Herrera** | Analista | Define y mantiene las dependencias del proyecto (`requirements.txt`) y responde por las funciones integradas del sistema, validando que cumplan los requerimientos. |
| **Andres Weil** | Tester y Documentación | Ejecuta las pruebas y documenta sus resultados. Propone mejoras y optimización del código, y es responsable de la hoja de estilos `style.css`. |
