from django import forms

from .models import AuditionApplication, Enquiry, GiftAidDeclaration


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


class GiftAidForm(forms.ModelForm):
    """
    Form for capturing HMRC-compliant Gift Aid declarations.
    Excludes the member field because we stamp it programmatically in the view.
    """

    class Meta:
        model = GiftAidDeclaration
        # Explicitly declare only the fields the user needs to manually fill out
        fields = [
            "first_name",
            "last_name",
            "address_line_1",
            "town_city",
            "postcode",
            "consent_given",
        ]

        # Add labels or clean placeholders to keep the layout professional
        labels = {
            "address_line_1": "Address Line 1",
            "town_city": "Town / City",
            "consent_given": "I confirm I am a UK taxpayer and want Clent Consort to claim Gift Aid on my subscriptions.",
        }
