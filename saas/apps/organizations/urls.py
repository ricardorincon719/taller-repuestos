from django.urls import path

from . import views

urlpatterns = [
    path("perfil/", views.organization_profile, name="organization-profile"),
    path("logo/<uuid:organization_id>/", views.organization_logo, name="organization-logo"),
    path("equipo/", views.team, name="organization-team"),
    path("equipo/<int:pk>/", views.member_update, name="organization-member-update"),
    path(
        "equipo/invitacion/<int:pk>/revocar/",
        views.invitation_revoke,
        name="organization-invitation-revoke",
    ),
    path("cambiar/", views.organization_switch, name="organization-switch"),
    path("exportar/", views.organization_export, name="organization-export"),
    path("eliminar/", views.organization_delete, name="organization-delete"),
    path("eliminar/cancelar/", views.organization_delete_cancel, name="organization-delete-cancel"),
    path(
        "invitacion/<uuid:token>/",
        views.invitation_accept,
        name="organization-invitation-accept",
    ),
]
