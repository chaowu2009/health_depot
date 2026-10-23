"""The fixed "About the person" block shown on every public intake form (English/Spanish).

Template questions (from the form builder) are added after this block.
"""

from django import forms
from django.utils import timezone

from apps.clients.models import Client

from .dynamic import PHONE_VALIDATOR

TEXT = {
    "en": {
        "about": "About the person being referred",
        "first_name": "First name",
        "last_name": "Last name",
        "dob": "Date of birth",
        "phone": "Phone number",
        "email": "Email (optional)",
        "zip": "ZIP code",
        "language": "Preferred language",
        "contact": "Best way to reach them",
        "consent_contact": "I agree that the health department and its partners may contact me.",
        "consent_share": "I agree that my information may be shared with the organizations "
        "helping me, only to coordinate my services.",
        "questions": "Questions",
        "submit": "Submit referral",
        "required": "Required",
        "thanks": "Thank you — your referral was received",
        "reference": "Your reference number",
        "next": "Someone will contact you soon. Please keep this number for your records.",
        "inactive": "This referral link is no longer active.",
        "switch": "Español",
        "switch_lang": "es",
        "privacy": "Your information is private and protected.",
        "phone_or_email": "Please give a phone number or an email address.",
        "dob_future": "Date of birth can't be in the future.",
    },
    "es": {
        "about": "Información de la persona referida",
        "first_name": "Nombre",
        "last_name": "Apellido",
        "dob": "Fecha de nacimiento",
        "phone": "Teléfono",
        "email": "Correo electrónico (opcional)",
        "zip": "Código postal",
        "language": "Idioma preferido",
        "contact": "Mejor forma de comunicarnos",
        "consent_contact": "Acepto que el departamento de salud y sus socios me contacten.",
        "consent_share": "Acepto que mi información se comparta con las organizaciones que me "
        "ayudan, solo para coordinar mis servicios.",
        "questions": "Preguntas",
        "submit": "Enviar referido",
        "required": "Obligatorio",
        "thanks": "Gracias — recibimos su referido",
        "reference": "Su número de referencia",
        "next": "Alguien se comunicará con usted pronto. Guarde este número.",
        "inactive": "Este enlace ya no está activo.",
        "switch": "English",
        "switch_lang": "en",
        "privacy": "Su información es privada y está protegida.",
        "phone_or_email": "Indique un teléfono o un correo electrónico.",
        "dob_future": "La fecha de nacimiento no puede ser futura.",
    },
}

LANGUAGES = ["English", "Spanish", "Other"]
LANGUAGE_LABELS = {"es": {"English": "Inglés", "Spanish": "Español", "Other": "Otro"}}
CONTACT_LABELS = {
    "en": dict(Client.ContactMethod.choices),
    "es": {"PHONE": "Llamada", "TEXT": "Mensaje de texto", "EMAIL": "Correo electrónico"},
}


class IdentityForm(forms.Form):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    phone = forms.CharField(
        max_length=20,
        required=False,
        validators=[PHONE_VALIDATOR],
        widget=forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"}),
    )
    email = forms.EmailField(required=False)
    zip_code = forms.RegexField(regex=r"^\d{5}(-\d{4})?$", max_length=10)
    preferred_language = forms.ChoiceField()
    preferred_contact_method = forms.ChoiceField(widget=forms.RadioSelect)
    consent_to_contact = forms.BooleanField()
    consent_to_share = forms.BooleanField()
    # Honeypot: hidden from people; bots fill it in.
    website = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"})
    )

    def __init__(self, *args, lang: str = "en", **kwargs):
        super().__init__(*args, **kwargs)
        self.lang = lang if lang in TEXT else "en"
        t = TEXT[self.lang]
        labels = {
            "first_name": t["first_name"],
            "last_name": t["last_name"],
            "date_of_birth": t["dob"],
            "phone": t["phone"],
            "email": t["email"],
            "zip_code": t["zip"],
            "preferred_language": t["language"],
            "preferred_contact_method": t["contact"],
            "consent_to_contact": t["consent_contact"],
            "consent_to_share": t["consent_share"],
        }
        for name, text in labels.items():
            self.fields[name].label = text
        lang_labels = LANGUAGE_LABELS.get(self.lang, {})
        self.fields["preferred_language"].choices = [(v, lang_labels.get(v, v)) for v in LANGUAGES]
        self.fields["preferred_contact_method"].choices = list(CONTACT_LABELS[self.lang].items())
        self.fields["preferred_contact_method"].initial = "PHONE"
        self.fields["preferred_language"].initial = "Spanish" if self.lang == "es" else "English"
        self.fields["website"].label = "Leave this empty"

    def clean_date_of_birth(self):
        dob = self.cleaned_data["date_of_birth"]
        if dob > timezone.localdate():
            raise forms.ValidationError(TEXT[self.lang]["dob_future"])
        return dob

    def clean(self):
        data = super().clean() or {}
        if not data.get("phone") and not data.get("email"):
            self.add_error("phone", TEXT[self.lang]["phone_or_email"])
        return data

    @property
    def is_bot(self) -> bool:
        return bool(self.cleaned_data.get("website")) if hasattr(self, "cleaned_data") else False
