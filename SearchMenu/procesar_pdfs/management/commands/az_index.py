import os
from SearchMenu.settings import *
from django.core.management.base import BaseCommand
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SimpleField, SearchFieldDataType
)
 
class Command(BaseCommand):
    help = "Crea el índice en Azure AI Search"
 
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("Conectando a Azure AI Search..."))
 
        client = SearchIndexClient(
            endpoint=AZURE_SEARCH_URL,
            credential=AzureKeyCredential(AZURE_SEARCH_API_KEY),
        )
 
        # Definir campos del índice
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchField(name="restaurant_id", type=SearchFieldDataType.String, searchable=False, filterable=True, retrievable=True),
            SearchField(name="restaurant_name", type=SearchFieldDataType.String, searchable=True, filterable=True, retrievable=True),
            SearchField(name="menu_id", type=SearchFieldDataType.String, searchable=False, filterable=True, retrievable=True),
            SearchField(name="menu_name", type=SearchFieldDataType.String, searchable=True, filterable=True, retrievable=True),
            SearchField(name="menu_price", type=SearchFieldDataType.Double, searchable=False, filterable=True, retrievable=True),
            SearchField(name="dish_name", type=SearchFieldDataType.String, searchable=True, filterable=True, retrievable=True),
            SearchField(name="dish_price", type=SearchFieldDataType.Double, searchable=False, filterable=True, retrievable=True),
            SearchField(name="dish_type", type=SearchFieldDataType.String, searchable=False, filterable=True, retrievable=True),
        ]
 
        index = SearchIndex(name=AZURE_SEARCH_INDEX, fields=fields)
 
        # Eliminar índice previo si existe
        try:
            client.delete_index(AZURE_SEARCH_INDEX)
            self.stdout.write(self.style.WARNING("Índice eliminado"))
        except Exception:
            self.stdout.write(self.style.NOTICE("No había un índice previo"))
 
        # Crear el nuevo índice
        client.create_index(index)
        self.stdout.write(self.style.SUCCESS("Índice creado correctamente"))