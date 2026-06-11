from django import forms

from .models import AuditionApplication, Enquiry


class EnquiryForm(forms.ModelForm):
    """Form to validate and save general website enquiries."""

    class Meta:
        model = Enquiry
        # These fields map exactly to your HTML input 'name' attributes
        fields = ["name", "email", "subject", "message"]


class AuditionApplicationForm(forms.ModelForm):
    """Form to validate and save prospective singer requests."""

    class Meta:
        model = AuditionApplication
        fields = ["name", "email", "voice_part", "experience"]
