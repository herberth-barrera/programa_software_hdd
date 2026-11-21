import io
from datetime import datetime

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PyPdfError
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

AZUL = colors.HexColor("#0f2a5f")
CELESTE = colors.HexColor("#e9eff9")
GRIS = colors.HexColor("#6a7893")


class ErrorExpediente(Exception):
    """Un documento no se pudo leer o unir; el mensaje se muestra al usuario."""


def _abrir(archivo):
    try:
        lector = PdfReader(archivo["ruta"])
        if lector.is_encrypted and not lector.decrypt(""):
            raise ErrorExpediente("«%s» está protegido con contraseña y no se puede unir al expediente."
                                  % archivo["documento"])
        return lector, len(lector.pages)
    except ErrorExpediente:
        raise
    except (PyPdfError, ValueError, OSError):
        raise ErrorExpediente("«%s» (%s) está dañado o no es un PDF legible."
                              % (archivo["documento"], archivo["nombre_original"]))


def _portada(empleado, archivos, paginas, primera, generado_por, logo):
    estilos = {
        "titulo": ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=22, textColor=AZUL, leading=26),
        "sub": ParagraphStyle("s", fontName="Helvetica", fontSize=11, textColor=GRIS, leading=14),
        "h2": ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=13, textColor=AZUL, spaceBefore=14, spaceAfter=6),
        "celda": ParagraphStyle("c", fontName="Helvetica", fontSize=9.5, leading=12),
        "pie": ParagraphStyle("p", fontName="Helvetica", fontSize=8.5, textColor=GRIS, leading=11),
    }
    salida = io.BytesIO()
    doc = SimpleDocTemplate(salida, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title="Expediente " + empleado["codigo"])
    historia = []
    if logo:
        ancho, alto = ImageReader(logo).getSize()
        historia.append(Image(logo, width=62 * mm, height=62 * mm * alto / ancho, hAlign="LEFT"))
        historia.append(Spacer(1, 8 * mm))
    historia.append(Paragraph("Expediente digital del colaborador", estilos["titulo"]))
    historia.append(Paragraph("Hospital de Diagnóstico · Talento Humano", estilos["sub"]))

    datos = [
        ["Nombre", empleado["nombre"], "Código", empleado["codigo"]],
        ["Puesto", empleado["puesto"], "Área", empleado["area"]],
        ["Sucursal", empleado["sucursal"], "Estado", empleado["estado"]],
        ["Ingreso", empleado["fecha_ingreso"].strftime("%d/%m/%Y"), "Documentos", str(len(archivos))],
    ]
    tabla_datos = Table([[Paragraph("<b>%s</b>" % a, estilos["celda"]), Paragraph(b, estilos["celda"]),
                          Paragraph("<b>%s</b>" % c, estilos["celda"]), Paragraph(d, estilos["celda"])]
                         for a, b, c, d in datos], colWidths=[24 * mm, 56 * mm, 26 * mm, 64 * mm])
    tabla_datos.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CELESTE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.white),
    ]))
    historia.append(Spacer(1, 8 * mm))
    historia.append(tabla_datos)

    historia.append(Paragraph("Índice de documentos", estilos["h2"]))
    filas = [["N.º", "Documento", "Versión", "Archivo", "Pág."]]
    pagina = primera
    for i, archivo in enumerate(archivos, start=1):
        filas.append([str(i), Paragraph(archivo["documento"], estilos["celda"]), "v%d" % archivo["version"],
                      Paragraph(archivo["nombre_original"], estilos["celda"]), str(pagina)])
        pagina += paginas[i - 1]
    indice = Table(filas, colWidths=[12 * mm, 66 * mm, 18 * mm, 62 * mm, 12 * mm], repeatRows=1)
    indice.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CELESTE]),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    historia.append(indice)
    historia.append(Spacer(1, 8 * mm))
    historia.append(Paragraph(
        "Generado el %s por %s. Contiene la versión más reciente de cada documento subido por el colaborador. "
        "Documento de uso interno." % (datetime.now().strftime("%d/%m/%Y %H:%M"), generado_por), estilos["pie"]))
    doc.build(historia)
    salida.seek(0)
    return salida


def construir_expediente(empleado, archivos, destino, generado_por, logo=None):
    """Une la portada y los PDF de `archivos` (cada uno con su 'ruta' en disco) en `destino`."""
    lectores = []
    paginas = []
    for archivo in archivos:
        lector, cuantas = _abrir(archivo)
        lectores.append(lector)
        paginas.append(cuantas)

    # La portada se arma dos veces: la primera para saber cuántas páginas ocupa
    # y la segunda con los números de página del índice ya correctos
    prueba = PdfReader(_portada(empleado, archivos, paginas, 2, generado_por, logo))
    portada = PdfReader(_portada(empleado, archivos, paginas, len(prueba.pages) + 1, generado_por, logo))

    escritor = PdfWriter()
    escritor.append(portada)
    for archivo, lector in zip(archivos, lectores):
        inicio = len(escritor.pages)
        escritor.append(lector)
        escritor.add_outline_item("%s (v%d)" % (archivo["documento"], archivo["version"]), inicio)
    escritor.add_metadata({
        "/Title": "Expediente %s - %s" % (empleado["codigo"], empleado["nombre"]),
        "/Author": "Hospital de Diagnóstico - Expedientes Digitales",
    })
    with open(destino, "wb") as salida:
        escritor.write(salida)
    return len(escritor.pages)
