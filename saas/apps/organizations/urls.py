from django.urls import path

from .views import organization_profile

urlpatterns = [
    path("perfil/", organization_profile, name="organization-profile"),
]
