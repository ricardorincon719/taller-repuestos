from django.urls import path

from .views import dashboard, public_home

urlpatterns = [
    path("", public_home, name="public-home"),
    path("panel/", dashboard, name="dashboard"),
]
