from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class ConsumidorRegisterForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2']

class RestauranteRegisterForm(UserCreationForm):
    email = forms.EmailField()
    nombre_restaurante = forms.CharField(max_length=100)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'nombre_restaurante', 'password1', 'password2']
