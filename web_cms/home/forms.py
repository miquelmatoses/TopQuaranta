from django import forms

from .models import CmsArtista


class CmsArtistaForm(forms.ModelForm):
    class Meta:
        model = CmsArtista
        # Incloem els camps que ja tenies + els 4 que volem obligar
        fields = [
            "nom",
            "generes",
            "territori",
            "comarca",
            "localitat",
            "dones",
            "agencia",
            "web",
            "viquipedia",
            "instagram",
            "youtube",
            "tiktok",
            "soundcloud",
            "bandcamp",
            "deezer",
            "bluesky",
            "myspace",
            "email",
            "telefon",
            "id_viasona",
            "bio",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ✅ ACI els fem obligatoris al formulari
        for f in ["nom", "localitat", "comarca", "territori"]:
            self.fields[f].required = True

    # (opcional però recomanat) Evita valors en blanc/després d'espais
    def clean_nom(self):
        v = (self.cleaned_data.get("nom") or "").strip()
        if not v:
            raise forms.ValidationError("El camp «nom» és obligatori.")
        return v

    def clean_localitat(self):
        v = (self.cleaned_data.get("localitat") or "").strip()
        if not v:
            raise forms.ValidationError("El camp «localitat» és obligatori.")
        return v

    def clean_comarca(self):
        v = (self.cleaned_data.get("comarca") or "").strip()
        if not v:
            raise forms.ValidationError("El camp «comarca» és obligatori.")
        return v

    def clean_territori(self):
        v = (self.cleaned_data.get("territori") or "").strip()
        if not v:
            raise forms.ValidationError("El camp «territori» és obligatori.")
        return v
