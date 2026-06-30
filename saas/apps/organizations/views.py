from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import translation
from django.utils.translation import gettext as _

from .forms import OrganizationProfileForm
from .services import get_current_membership


@login_required
def organization_profile(request):
    membership = get_current_membership(request.user)
    organization = membership.organization
    form = OrganizationProfileForm(request.POST or None, instance=organization)
    if request.method == "POST" and form.is_valid():
        organization = form.save()
        translation.activate(organization.language)
        request.LANGUAGE_CODE = translation.get_language()
        messages.success(request, _("Perfil del negocio actualizado."))
        return redirect("organization-profile")

    return render(
        request,
        "organizations/profile.html",
        {
            "form": form,
            "membership": membership,
            "organization": organization,
        },
    )
