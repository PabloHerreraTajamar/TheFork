from django.shortcuts import render
import os
import json
import re
from django.conf import settings
from .models import Restaurante, Menu, Plato
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from SearchMenu.settings import AZURE_SEARCH_URL, AZURE_SEARCH_API_KEY, AZURE_SEARCH_INDEX

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

# Interpretar el menu con Azure OpenAI
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

# Procesar PDFs en la base de datos
def procesar_pdf(request):
    """Vista de Django para procesar un PDF, guardar la información en la BD e indexar los platos en Azure AI Search."""
    resultado = None
    menu_info = None  # Inicializar la variable para evitar errores

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

            # Crear platos para cada categoría
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

            # Llamar al método de indexación de platos en Azure AI Search
            indexing_result = index_dishes_task()

            # Enviar los datos al template sin convertirlos a JSON
            resultado = menu_info
        else:
            resultado = {"error": "No se pudo extraer información válida del PDF."}  # Asegurar que siempre haya un resultado

    return render(request, "procesar_pdfs/upload.html", {"resultado": resultado})


# Indexar platos en AI Search
def index_dishes_task():
    print("*" * 50)
    print("📡 Indexando platos en Azure AI Search...")

    # Conectar con Azure AI Search
    client = SearchClient(
        endpoint=AZURE_SEARCH_URL,
        index_name=AZURE_SEARCH_INDEX,
        credential=AzureKeyCredential(AZURE_SEARCH_API_KEY),
    )

    documents = []

    # Obtener los platos con sus relaciones de menú y restaurante
    for dish in Plato.objects.select_related('menu__restaurante'):
        menu = dish.menu
        restaurante = menu.restaurante if menu else None

        documents.append({
            "id": f"dish-{dish.id}",
            "restaurant_id": f"restaurant-{restaurante.id}" if restaurante else "",
            "restaurant_name": restaurante.nombre if restaurante else "",
            "menu_id": f"menu-{menu.id}" if menu else "",
            "menu_name": menu.nombre_menu if menu else "",
            "menu_price": float(menu.precio) if menu and menu.precio else 0.0,
            "dish_name": dish.nombre_plato,
            "dish_type": dish.get_tipo_plato_display(),
        })

    print("📄 Documentos a indexar:", json.dumps(documents, indent=2))  # Debug

    if documents:
        try:
            response = client.upload_documents(documents=documents)
            print(f"✅ {len(documents)} platos indexados correctamente.")
            return f"✅ {len(documents)} platos indexados en Azure AI Search."
        except Exception as e:
            print(f"❌ Error al indexar: {e}")
            return f"❌ Error al indexar platos: {e}"

    print("⚠️ No hay platos para indexar.")
    print("*" * 50)
    return "⚠️ No hay platos para indexar."

# Búsqueda de platos
def search_dishes(request):
    query = request.GET.get('q', '')
    show_all = request.GET.get('show_all', False)  # Si se presiona el botón, esta variable será `True`
    menus = []

    if show_all:  
        # Obtener todos los menús guardados en la base de datos
        all_menus = Menu.objects.select_related('restaurante').prefetch_related('platos').all()

        for menu_obj in all_menus:
            dishes_group = {"Primero": [], "Segundo": [], "Postre": []}

            for dish in menu_obj.platos.all():
                dish_type = dish.get_tipo_plato_display()
                if dish_type in dishes_group:
                    dishes_group[dish_type].append(dish.nombre_plato)
                else:
                    if "Otros" not in dishes_group:
                        dishes_group["Otros"] = []
                    dishes_group["Otros"].append(dish.nombre_plato)

            menu_data = {
                "menu_name": menu_obj.nombre_menu,
                "menu_price": float(menu_obj.precio),
                "restaurant_name": menu_obj.restaurante.nombre,
                "dishes": dishes_group,
            }
            menus.append(menu_data)

    elif query:
        # Si el usuario está buscando un menú específico, hacer la búsqueda en Azure Search
        search_client = SearchClient(
            endpoint=AZURE_SEARCH_URL,
            index_name=AZURE_SEARCH_INDEX,
            credential=AzureKeyCredential(AZURE_SEARCH_API_KEY),
        )

        search_results = search_client.search(
            search_text=f'"{query}"',
            query_type="full",
            search_mode="all"
        )

        matching_menu_ids = set()
        for doc in search_results:
            m_id = doc.get("menu_id", "")
            if m_id.startswith("menu-"):
                numeric_id = m_id.split("-")[1]
                matching_menu_ids.add(numeric_id)

        for menu_id in matching_menu_ids:
            try:
                menu_obj = Menu.objects.get(id=menu_id)
            except Menu.DoesNotExist:
                continue

            dishes_group = {"Primero": [], "Segundo": [], "Postre": []}
            for dish in menu_obj.platos.all():
                dish_type = dish.get_tipo_plato_display()
                if dish_type in dishes_group:
                    dishes_group[dish_type].append(dish.nombre_plato)
                else:
                    if "Otros" not in dishes_group:
                        dishes_group["Otros"] = []
                    dishes_group["Otros"].append(dish.nombre_plato)

            menu_data = {
                "menu_name": menu_obj.nombre_menu,
                "menu_price": float(menu_obj.precio),
                "restaurant_name": menu_obj.restaurante.nombre,
                "dishes": dishes_group,
            }
            menus.append(menu_data)

    context = {
        'query': query,
        'results': menus,
        'show_all': show_all  # Para saber si se presionó el botón
    }
    return render(request, "procesar_pdfs/search_dishes.html", context)
