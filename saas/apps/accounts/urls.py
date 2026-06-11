from django.urls import path

from . import views

urlpatterns = [
    path("registro/", views.register, name="register"),
    path("activar/<uidb64>/<token>/", views.activate_account, name="activate-account"),
    path("reenviar-activacion/", views.resend_activation, name="resend-activation"),
]
