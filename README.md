# Expedientes Digitales · Hospital de Diagnóstico

Sistema web interno para la gestión del expediente documental del personal del Hospital de Diagnóstico. Centraliza los perfiles de los colaboradores, controla qué documentos han entregado y conserva, dentro de la propia base de datos, cada archivo y su historial de versiones.

![Python](https://img.shields.io/badge/Python-3.10%2B-1d4796) ![Flask](https://img.shields.io/badge/Flask-3.x-0f2a5f) ![MySQL](https://img.shields.io/badge/MySQL%20%2F%20MariaDB-XAMPP-6f82a0)

---

## Contenido
1. [Resumen ejecutivo](#resumen-ejecutivo)
2. [Funcionalidades](#funcionalidades)
3. [Arquitectura y tecnologías](#arquitectura-y-tecnologías)
4. [Instalación y ejecución](#instalación-y-ejecución)
5. [Estructura del proyecto](#estructura-del-proyecto)
6. [Modelo de datos](#modelo-de-datos)
7. [Gestión de archivos](#gestión-de-archivos)
8. [Reglas de negocio y seguridad](#reglas-de-negocio-y-seguridad)
9. [Rutas del sistema](#rutas-del-sistema)
10. [Equipo y responsabilidades](#equipo-y-responsabilidades)

---

## Resumen ejecutivo
El área de Talento Humano necesita saber, en cualquier momento, qué empleados tienen su expediente completo, cuáles tienen documentos vencidos y cuáles no han entregado nada. Este sistema responde esas preguntas desde un panel único, con una interfaz alineada a la identidad visual del hospital.

| Indicador | Detalle |
|---|---|
| Documentos por expediente | 12 tipos de documento por empleado |
| Tamaño máximo por archivo | 1 GB, almacenado como BLOB en MySQL |
| Formatos admitidos | PDF, DOC y DOCX |
| Códigos de empleado | Automáticos y únicos (`HDD-0001`, `HDD-0002`...) |
| Sucursales | Escalón, Santa Elena y Colonia Médica |

## Funcionalidades

**Gestión de personal**
- Registro de empleados con código **generado automáticamente**; el código nunca se repite, aunque el perfil se elimine de la base de datos.
- Menús desplegables para puesto, área, sucursal y estado laboral (Activo, Inactivo, Licencia médica, Vacaciones).
- Edición completa del perfil y del checklist de documentos entregados. El código es inmutable.
- Eliminación **restrictiva**: un perfil con archivos o documentos asociados no puede borrarse desde el sistema.

**Gestión documental**
- Subida de documentos con **arrastrar y soltar**, validación inmediata y barra de progreso.
- **Control de versiones**: subir un documento nunca reemplaza al anterior; se conserva todo el historial.
- Estado automático por documento: *Vigente*, *Vencido* o *Versión anterior*, con aviso de días para el vencimiento.
- Descarga de cualquier versión.

**Analítica y control**
- Panel de indicadores con expedientes completos, con vencidos y documentos subidos.
- Resumen que clasifica cada expediente: *Completo*, *Con documentos vencidos*, *Incompleto en proceso* e *Incompleto sin archivos*.

**Continuidad operativa**
- Si Apache o MySQL se detienen en el Panel de Control de XAMPP, el sistema deja de operar y muestra una pantalla con el estado de cada servicio, en lugar de fallar de forma confusa.

## Arquitectura y tecnologías

| Capa | Tecnología | Responsabilidad |
|---|---|---|
| Presentación | HTML, plantillas Jinja2, CSS, JavaScript | Interfaz con identidad del hospital, formularios y subida con arrastre |
| Aplicación | Python y Flask | Rutas, validaciones y reglas de negocio |
| Datos | MySQL / MariaDB (XAMPP) vía `mysql-connector-python` | Persistencia relacional y almacenamiento de archivos |

Decisiones de diseño relevantes:
- **Consultas parametrizadas** (`%s`) en todo el acceso a datos, sin concatenar texto del usuario en el SQL.
- **Archivos por fragmentos**: cada archivo se divide en bloques de 256 KB. Ningún paquete supera el límite por defecto de MySQL (`max_allowed_packet`), y la descarga se entrega en flujo sin cargar el archivo completo en memoria.
- **Subida transaccional**: el archivo se guarda con un único `commit`; si algo falla, no queda información a medias.
- **Integridad referencial** con llaves foráneas y `ON DELETE CASCADE` en las tablas dependientes.

## Instalación y ejecución

**Requisitos:** Python 3.10 o superior y XAMPP con Apache y MySQL.

1. Abrir el Panel de Control de XAMPP e **iniciar Apache y MySQL**.
2. Entrar a `http://localhost/phpmyadmin/`, pestaña **Importar**, elegir `crear_bd.sql` y pulsar **Continuar**. El script crea la base `hospital_hdd` y carga datos de ejemplo.
   > Atención: el script elimina y recrea las tablas. Ejecutarlo de nuevo borra los datos existentes.
3. (Recomendado) Crear y activar un entorno virtual:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
4. Instalar las dependencias:
   ```
   python -m pip install -r requirements.txt
   ```
5. Ejecutar la aplicación desde la carpeta del proyecto:
   ```
   python app.py
   ```
6. Abrir `http://127.0.0.1:5000/empleados`.

Conexión a la base de datos: usuario `root` sin contraseña (valores por defecto de XAMPP), definidos en la función `conectar()` de `app.py`.

**Solución de problemas**

| Mensaje | Causa probable | Solución |
|---|---|---|
| El sistema no está disponible | Apache o MySQL detenidos | Iniciarlos en XAMPP y pulsar *Volver a comprobar* |
| `Table '...' doesn't exist` | Base de datos con esquema anterior | Volver a importar `crear_bd.sql` |
| `No module named 'flask'` | Dependencias sin instalar | Ejecutar `python -m pip install -r requirements.txt` |

## Estructura del proyecto
```
.
├── app.py               Rutas de Flask, validaciones y lógica del sistema
├── crear_bd.sql         Esquema de la base de datos y datos de ejemplo
├── requirements.txt     Dependencias: flask, mysql-connector-python
├── README.md
├── templates/
│   ├── base.html        Estructura común: menú lateral, logo y mensajes
│   ├── empleados.html   Panel principal con indicadores y listado
│   ├── nuevo.html       Registro de empleados
│   ├── editar.html      Edición de perfil y checklist
│   ├── archivos.html    Archivos y versiones de un empleado
│   ├── subir.html       Subida de documentos (multipart/form-data)
│   ├── resumen.html     Clasificación de expedientes
│   ├── servicios.html   Pantalla de servicios detenidos
│   └── error.html       Errores controlados
└── static/
    ├── style.css        Hoja de estilos única del sistema
    ├── subir.js         Arrastrar y soltar, validación y progreso
    └── logo.png         Logotipo del hospital
```

## Modelo de datos
Base de datos `hospital_hdd`.

| Tabla | Propósito | Campos principales |
|---|---|---|
| `secuencia_codigos` | Contador de códigos de empleado; solo avanza | `nombre` (PK), `ultimo` |
| `empleados` | Perfil del colaborador | `id` (PK), `codigo` (único), `nombre`, `puesto`, `area`, `sucursal`, `estado`, `fecha_ingreso` |
| `documentos` | Catálogo de documentos requeridos | `id` (PK), `nombre`, `requiere_vencimiento` |
| `expediente` | Checklist de entrega por empleado | `empleado_id` (PK, FK), `documento_id` (PK, FK), `entregado` |
| `archivos` | Cada versión subida | `id` (PK), `empleado_id` (FK), `documento_id` (FK), `version`, `nombre_original`, `tamano`, `contenido` (LONGBLOB), `fecha_vencimiento`, `fecha_subida` |
| `archivo_partes` | Resto de cada archivo en bloques de 256 KB | `archivo_id` (PK, FK), `orden` (PK), `contenido` (LONGBLOB) |

Relaciones e integridad:
- `expediente`, `archivos` y `archivo_partes` dependen de su tabla padre con `ON DELETE CASCADE`.
- `UNIQUE (empleado_id, documento_id, version)` impide duplicar una versión.
- `empleados.codigo` es único.

## Gestión de archivos
- El formulario usa `method="POST"` y `enctype="multipart/form-data"`; Flask recibe el archivo con `request.files`.
- **Validaciones:** documento seleccionado, archivo presente, extensión permitida, archivo no vacío, tamaño máximo de 1 GB, fecha de vencimiento obligatoria para el DUI y fecha válida. Se verifican en el navegador y de nuevo en el servidor.
- **Versionado:** la versión siguiente se calcula con `SELECT MAX(version)`; la primera es 1.
- **Almacenamiento:** el primer bloque de 256 KB se guarda en `archivos.contenido` y el resto, en `archivo_partes`.
- **Estados** (decididos con `if/elif/else`):
  - *Versión anterior*: existe otra más reciente del mismo documento.
  - *Vencido*: es la versión más reciente y su fecha de vencimiento ya pasó.
  - *Vigente*: es la versión más reciente y no está vencida.
- Un archivo de 1 GB requiere tiempo de subida y espacio libre en el disco donde XAMPP guarda sus datos.
- Se recomienda trabajar solo con documentos de prueba, nunca con documentos personales reales.

## Reglas de negocio y seguridad
- El código de empleado lo asigna el servidor; cualquier valor enviado desde el formulario se ignora.
- Los menús desplegables se validan también en el servidor: un valor fuera de las listas se rechaza.
- Un perfil solo puede eliminarse si no tiene archivos ni documentos entregados; en caso contrario, se recomienda cambiar su estado a *Inactivo*.
- Los nombres de archivo se limpian y nunca se usan como ruta en disco, porque el contenido vive en la base de datos.
- Todas las consultas son parametrizadas.

## Rutas del sistema

| Ruta | Método | Función |
|---|---|---|
| `/empleados` | GET | Panel con indicadores y listado de empleados |
| `/empleados/nuevo` | GET, POST | Registro con código automático |
| `/empleados/editar/<id>` | GET, POST | Edición de perfil y checklist |
| `/empleados/eliminar/<id>` | POST | Eliminación restrictiva |
| `/empleados/<id>/archivos` | GET | Archivos y versiones del empleado |
| `/empleados/<id>/archivos/nuevo` | GET, POST | Subida de un documento (nueva versión) |
| `/archivos/<id>/descargar` | GET | Descarga de una versión |
| `/resumen` | GET | Clasificación de expedientes y contadores |

## Equipo y responsabilidades

| Integrante | Rol | Responsabilidades |
|---|---|---|
| **Herberth Barrera** | Tech Lead | Lidera la integración técnica y la armonización del código fuente (`app.py`). Diseña y mantiene la interfaz gráfica del sistema en HTML (`templates/`), garantizando coherencia visual y experiencia de usuario. |
| **Hector Calderon** | Developer | Responsable del manejo de la información y la conexión con la base de datos: consultas, acceso a datos y persistencia. Mantiene los recursos de la carpeta `static/`. |
| **Camila Herrera** | Analista | Define y mantiene las dependencias del proyecto (`requirements.txt`) y responde por las funciones integradas del sistema, validando que cumplan los requerimientos. |
| **Andres Weil** | Tester y Documentación | Ejecuta las pruebas y documenta sus resultados. Propone mejoras y optimización del código, y es responsable de la hoja de estilos `style.css`. |
