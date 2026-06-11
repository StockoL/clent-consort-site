from django import forms

from .models import AuditionApplication, Enquiry, GiftAidDeclaration


class EnquiryForm(forms.ModelForm):
    """Form for processing public contact and booking enquiries."""

    class Meta:
        model = Enquiry
        fields = ["name", "email", "subject", "message"]
        widgets = {
            "message": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Type your message here..."}
            ),
            "name": forms.TextInput(attrs={"placeholder": "Jane Doe"}),
            "email": forms.EmailInput(attrs={"placeholder": "jane@example.com"}),
        }


class AuditionForm(forms.ModelForm):
    """Form for prospective singers applying to audition."""

    class Meta:
        model = AuditionApplication
        fields = ["name", "email", "voice_part", "experience"]
        widgets = {
            "experience": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Tell us a bit about your choral experience...",
                }
            ),
            "name": forms.TextInput(attrs={"placeholder": "John Smith"}),
            "email": forms.EmailInput(attrs={"placeholder": "john@example.com"}),
        }


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
