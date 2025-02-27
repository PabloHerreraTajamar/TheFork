from django.contrib import admin
from .models import Restaurante, Menu, Plato

class PlatoInline(admin.TabularInline):  # Muestra los platos en formato tabla
    model = Plato
    extra = 1  # Número de filas vacías adicionales para agregar nuevos platos

class MenuAdmin(admin.ModelAdmin):
    list_display = ('nombre_menu', 'restaurante', 'precio')
    inlines = [PlatoInline]  # Agrega los platos dentro de la vista del menú

admin.site.register(Restaurante)
admin.site.register(Menu, MenuAdmin)
