from django.urls import path
from .views import home, procesar_pdf, search_dishes

urlpatterns = [
    path('', home, name='home'),  # Página principal
    path('upload/', procesar_pdf, name='procesar_pdf'),  # Página de subida de PDFs
    path('search/', search_dishes, name='search_dishes'), # Página de búsqueda de platos
]
