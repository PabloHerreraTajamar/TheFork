from django.shortcuts import render
from django.http import JsonResponse
import os
import json
import re
from django.conf import settings
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI

# Inicializar el cliente de Document Intelligence
document_analysis_client = DocumentAnalysisClient(
    endpoint=settings.AZURE_FORM_RECOGNIZER_ENDPOINT,
    credential=AzureKeyCredential(settings.AZURE_FORM_RECOGNIZER_KEY)
)

# Inicializar el cliente de Azure OpenAI
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

    # Obtener la respuesta y convertirla a JSON
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
            resultado = json.dumps(menu_info, indent=4, ensure_ascii=False)
        else:
            resultado = "Error: No se pudo extraer información válida."

    return render(request, "procesar_pdfs/upload.html", {"resultado": resultado})

from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import ConsumidorRegisterForm, RestauranteRegisterForm

def register_consumidor(request):
    if request.method == 'POST':
        form = ConsumidorRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'consumidor'
            user.save()
            login(request, user)
            return redirect('dashboard_consumidor')  # Redirige al dashboard de consumidores
    else:
        form = ConsumidorRegisterForm()
    return render(request, 'register_consumidor.html', {'form': form})

def register_restaurante(request):
    if request.method == 'POST':
        form = RestauranteRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'restaurante'
            user.save()
            login(request, user)
            return redirect('dashboard_restaurante')  # Redirige al dashboard de restaurantes
    else:
        form = RestauranteRegisterForm()
    return render(request, 'register_restaurante.html', {'form': form})
