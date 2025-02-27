from django.shortcuts import render
from django.http import JsonResponse
import os
import json
import re
from django.conf import settings
from .models import Restaurante, Menu, Plato

from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI

def home(request):
    """Vista de la página principal con un botón para subir PDFs."""
    return render(request, "procesar_pdfs/home.html")

document_analysis_client = DocumentAnalysisClient(
    endpoint=settings.AZURE_FORM_RECOGNIZER_ENDPOINT,
    credential=AzureKeyCredential(settings.AZURE_FORM_RECOGNIZER_KEY)
)

client = AzureOpenAI(
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_key=settings.AZURE_OPENAI_API_KEY,
    api_version="2024-05-01-preview"
)

def extract_text_from_pdf(pdf_path):
    """Extrae texto de un archivo PDF usando Azure Document Intelligence."""
    with open(pdf_path, "rb") as f:
        poller = document_analysis_client.begin_analyze_document("prebuilt-layout", document=f)
        result = poller.result()

    extracted_text = ""
    for page in result.pages:
        for line in page.lines:
            extracted_text += line.content + "\n"

    return extracted_text

def fix_json(json_str):
    """Intenta corregir un JSON mal formado."""
    try:
        # Eliminar texto adicional antes o después del JSON
        json_str = re.sub(r'^[^{]*', '', json_str)  # Eliminar todo antes del primer {
        json_str = re.sub(r'[^}]*$', '', json_str)  # Eliminar todo después del último }
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None

def interpret_menu_text(text):
    """Interpreta el texto del menú usando Azure OpenAI y devuelve un diccionario."""
    prompt = f"""Extrae la siguiente información del siguiente texto de un menú de restaurante y devuélvela en formato JSON:
    - "nombre_restaurante" (string)
    - "primeros_platos" (lista de strings)
    - "segundos_platos" (lista de strings)
    - "postres" (lista de strings)
    - "precio" (string)

    El JSON debe estar bien formado y no contener texto adicional. Solo devuelve el JSON.

    Texto:
    {text}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Cambia esto al modelo que estés usando
        messages=[
            {"role": "system", "content": "Eres un asistente que extrae información de menús de restaurantes y la devuelve en formato JSON."},
            {"role": "user", "content": prompt}
        ]
    )

    response_text = response.choices[0].message.content
    try:
        menu_info = json.loads(response_text)
    except json.JSONDecodeError:
        # Intentar corregir el JSON si no es válido
        menu_info = fix_json(response_text)
        if not menu_info:
            return None

    return menu_info

def procesar_pdf(request):
    """Vista de Django para procesar un PDF y mostrar el resultado en la pantalla."""
    resultado = None

    if request.method == "POST" and request.FILES.get("pdf"):
        pdf_file = request.FILES["pdf"]
        pdf_path = os.path.join(settings.MEDIA_ROOT, pdf_file.name)

        # Guardar el archivo temporalmente
        with open(pdf_path, "wb") as f:
            for chunk in pdf_file.chunks():
                f.write(chunk)

        # Extraer texto del PDF
        extracted_text = extract_text_from_pdf(pdf_path)

        # Interpretar el texto del menú
        menu_info = interpret_menu_text(extracted_text)

        # Eliminar el archivo temporal
        os.remove(pdf_path)

        if menu_info:
            # -- GUARDAR EN LA BASE DE DATOS --
            nombre_restaurante = menu_info.get("nombre_restaurante", "Desconocido")
            primeros_platos = menu_info.get("primeros_platos", [])
            segundos_platos = menu_info.get("segundos_platos", [])
            postres = menu_info.get("postres", [])
            precio_str = menu_info.get("precio", "0")

            # Convertir el precio extraído a decimal o float
            # Ejemplo simple: buscar la primera coincidencia numérica
            match = re.search(r"(\d+(?:\.\d+)?)", precio_str)
            if match:
                precio_valor = float(match.group(1))
            else:
                precio_valor = 0.0

            # Crear o recuperar el restaurante
            restaurante_obj, _ = Restaurante.objects.get_or_create(nombre=nombre_restaurante)

            # Crear el menú
            menu_obj = Menu.objects.create(
                restaurante=restaurante_obj,
                nombre_menu="Menú del día",
                precio=precio_valor
            )

            # Crear platos
            for plato in primeros_platos:
                Plato.objects.create(
                    menu=menu_obj,
                    nombre_plato=plato,
                    tipo_plato='PRIMERO'
                )

            for plato in segundos_platos:
                Plato.objects.create(
                    menu=menu_obj,
                    nombre_plato=plato,
                    tipo_plato='SEGUNDO'
                )

            for plato in postres:
                Plato.objects.create(
                    menu=menu_obj,
                    nombre_plato=plato,
                    tipo_plato='POSTRE'
                )

            # ----------------------------------------------------

            resultado = json.dumps(menu_info, indent=4, ensure_ascii=False)
        else:
            resultado = "Error: No se pudo extraer información válida."

    return render(request, "procesar_pdfs/upload.html", {"resultado": resultado})
