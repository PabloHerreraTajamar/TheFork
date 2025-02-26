import os
import json
import re
from dotenv import load_dotenv
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Configurar las credenciales de Azure Document Intelligence
form_recognizer_endpoint = os.getenv("AZURE_FORM_RECOGNIZER_ENDPOINT")
form_recognizer_key = os.getenv("AZURE_FORM_RECOGNIZER_KEY")

# Configurar las credenciales de Azure OpenAI
azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_openai_key = os.getenv("AZURE_OPENAI_API_KEY")
api_version="2024-05-01-preview"  # Asegúrate de usar la versión correcta

# Inicializar el cliente de Document Intelligence
document_analysis_client = DocumentAnalysisClient(
    endpoint=form_recognizer_endpoint, credential=AzureKeyCredential(form_recognizer_key)
)

# Inicializar el cliente de Azure OpenAI
client = AzureOpenAI(
    azure_endpoint=azure_openai_endpoint,
    api_key=azure_openai_key,
    api_version=api_version
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
            print("Error: No se pudo decodificar la respuesta como JSON.")
            return None

    return menu_info

def process_pdf_folder(folder_path):
    """Procesa todos los PDFs en una carpeta y muestra la información del menú en formato JSON."""
    for filename in os.listdir(folder_path):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(folder_path, filename)
            print(f"Procesando {filename}...")
            extracted_text = extract_text_from_pdf(pdf_path)
            menu_info = interpret_menu_text(extracted_text)

            if menu_info:
                print(json.dumps(menu_info, indent=4, ensure_ascii=False))  # Imprimir en formato JSON
            else:
                print("No se pudo extraer información válida.")
            print("-" * 40)

if __name__ == "__main__":
    folder_path = "pdf/"  # Cambia esto por la ruta a tu carpeta de PDFs
    process_pdf_folder(folder_path)