from django.db import models

class Restaurante(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre


class Menu(models.Model):
    restaurante = models.ForeignKey(Restaurante, on_delete=models.CASCADE)
    nombre_menu = models.CharField(max_length=100, default="Menú del día")
    precio = models.DecimalField(max_digits=6, decimal_places=2)

    def __str__(self):
        # Muestra algo como: "Menú del día (Restaurante XYZ)"
        return f"{self.nombre_menu} ({self.restaurante.nombre})"


class Plato(models.Model):
    TIPO_PLATO_CHOICES = [
        ('PRIMERO', 'Primero'),
        ('SEGUNDO', 'Segundo'),
        ('POSTRE', 'Postre'),
    ]

    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name='platos')
    nombre_plato = models.CharField(max_length=100)
    tipo_plato = models.CharField(max_length=7, choices=TIPO_PLATO_CHOICES)

    def __str__(self):
        return f"{self.nombre_plato} - {self.get_tipo_plato_display()}"