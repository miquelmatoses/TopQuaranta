from django import forms
from django.contrib.auth import get_user_model

from music.models import Artista

from .models import UserArtista

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
        email = self.cleaned_data["email"]
        if Usuari.objects.filter(email=email).exists():
            raise forms.ValidationError("Ja existeix un compte amb aquest correu.")
        return email

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


class SollicitudArtistaForm(forms.ModelForm):
    """Form for requesting artist verification."""

    artista = forms.ModelChoiceField(
        queryset=Artista.objects.filter(aprovat=True).order_by("nom"),
        label="Artista",
        widget=forms.Select(attrs={"class": "filter-search"}),
    )
    sollicitud_text = forms.CharField(
        label="Justificació",
        widget=forms.Textarea(attrs={
            "rows": 4,
            "placeholder": "Explica breument per què ets aquest artista o el representes.",
        }),
    )

    class Meta:
        model = UserArtista
        fields = ("artista", "sollicitud_text")
