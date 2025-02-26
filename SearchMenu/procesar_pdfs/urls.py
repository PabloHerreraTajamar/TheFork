from django.urls import path
from . import views

urlpatterns = [
    path("procesar-pdf/", views.procesar_pdf, name="procesar_pdf"),
]