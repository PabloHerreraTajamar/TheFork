import os
from django.core.management.base import BaseCommand
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SimpleField, SearchFieldDataType
)
from procesar_pdfs.models import Restaurante, Menu, Plato  # Asegúrate de que sea el import correcto
from SearchMenu.settings import AZURE_SEARCH_URL, AZURE_SEARCH_API_KEY, AZURE_SEARCH_INDEX

class Command(BaseCommand):
    help = "Crea el índice en Azure AI Search y lo llena con datos de la BD"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("Conectando a Azure AI Search..."))

        # Cliente de Azure AI Search
        client = SearchIndexClient(
            endpoint=AZURE_SEARCH_URL,
            credential=AzureKeyCredential(AZURE_SEARCH_API_KEY),
        )

        # Definir los campos del índice basados en los modelos de Django
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchField(name="restaurant_id", type=SearchFieldDataType.String, filterable=True, retrievable=True),
            SearchField(name="restaurant_name", type=SearchFieldDataType.String, searchable=True, filterable=True, retrievable=True),
            SearchField(name="menu_id", type=SearchFieldDataType.String, filterable=True, retrievable=True),
            SearchField(name="menu_name", type=SearchFieldDataType.String, searchable=True, filterable=True, retrievable=True),
            SearchField(name="menu_price", type=SearchFieldDataType.Double, filterable=True, retrievable=True),
            SearchField(name="dish_name", type=SearchFieldDataType.String, searchable=True, filterable=True, retrievable=True),
            SearchField(name="dish_type", type=SearchFieldDataType.String, filterable=True, retrievable=True),
        ]

        index = SearchIndex(name=AZURE_SEARCH_INDEX, fields=fields)

        # Eliminar índice previo si existe
        try:
            client.delete_index(AZURE_SEARCH_INDEX)
            self.stdout.write(self.style.WARNING("Índice anterior eliminado."))
        except Exception:
            self.stdout.write(self.style.NOTICE("No había un índice previo."))

        # Crear el nuevo índice
        client.create_index(index)
        self.stdout.write(self.style.SUCCESS("Índice creado correctamente."))

        # Indexar datos desde la base de datos
        self.indexar_datos()

    def indexar_datos(self):
        """ Obtiene datos de la BD y los sube a Azure AI Search """
        from azure.search.documents import SearchClient

        search_client = SearchClient(
            endpoint=AZURE_SEARCH_URL,
            index_name=AZURE_SEARCH_INDEX,
            credential=AzureKeyCredential(AZURE_SEARCH_API_KEY),
        )

        documentos = []
        for restaurante in Restaurante.objects.all():
            for menu in restaurante.menu_set.all():
                for plato in menu.platos.all():
                    doc = {
                        "id": f"{restaurante.id}-{menu.id}-{plato.id}",
                        "restaurant_id": str(restaurante.id),
                        "restaurant_name": restaurante.nombre,
                        "menu_id": str(menu.id),
                        "menu_name": menu.nombre_menu,
                        "menu_price": float(menu.precio),
                        "dish_name": plato.nombre_plato,
                        "dish_type": plato.tipo_plato,
                    }
                    documentos.append(doc)

        if documentos:
            search_client.upload_documents(documents=documentos)
            self.stdout.write(self.style.SUCCESS(f"{len(documentos)} documentos indexados correctamente."))
        else:
            self.stdout.write(self.style.WARNING("No hay datos para indexar."))
