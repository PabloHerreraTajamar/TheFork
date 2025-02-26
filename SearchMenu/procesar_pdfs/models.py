from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('consumidor', 'Consumidor'),
        ('restaurante', 'Restaurante'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    nombre_restaurante = models.CharField(max_length=100, blank=True, null=True)  # Solo para restaurantes

    def __str__(self):
        return self.username
