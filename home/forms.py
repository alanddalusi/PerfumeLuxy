from django import forms

from .models import Subscriber


LAUNCH_CONSENT_VERSION = "launch-email-v2"


class SubscribeForm(forms.ModelForm):
    consent = forms.BooleanField(
        error_messages={"required": "Confirma que quieres recibir avisos de lanzamiento."}
    )

    class Meta:
        model = Subscriber
        fields = ("email",)

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def save(self, commit=True):
        if not commit:
            return super().save(commit=False)
        subscriber, _ = Subscriber.objects.get_or_create(
            email=self.cleaned_data["email"], consent_version=LAUNCH_CONSENT_VERSION,
        )
        return subscriber
