from django.urls import path
from .views import home, procesar_pdf

urlpatterns = [
    path('', home, name='home'),  # Página principal
    path('upload/', procesar_pdf, name='procesar_pdf'),  # Página de subida de PDFs
]
