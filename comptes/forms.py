"""Forms used by the Django-rendered auth flow.

Since Sprint 4 only the signup form survives as a Django form; the
artist-gestió / proposta forms moved to React and hit
`/api/v1/compte/{solicituds,propostes}/` directly.
"""

from django import forms
from django.contrib.auth import get_user_model

Usuari = get_user_model()


class RegistreForm(forms.ModelForm):
    """Registration form with email and password."""

    password1 = forms.CharField(
        label="Contrasenya",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Repeteix la contrasenya",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = Usuari
        fields = ("email",)

    def clean_email(self) -> str:
        # NOTE (S5): we deliberately do NOT tell the user whether an email
        # is already registered — that would leak account existence to any
        # passer-by. The view handles collisions silently and shows the same
        # "check your email" page regardless.
        return self.cleaned_data["email"]

    def clean_password2(self) -> str:
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Les contrasenyes no coincideixen.")
        return p2

    def save(self, commit: bool = True) -> Usuari:
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.set_password(self.cleaned_data["password1"])
        user.is_active = False  # Inactive until email confirmed
        if commit:
            user.save()
        return user
