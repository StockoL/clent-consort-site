from django import forms
from django.contrib.auth.models import User

from .models import (
    AuditionApplication,
    CommitteeDocument,
    Enquiry,
    GiftAidDeclaration,
    MemberProfile,
)


class EnquiryForm(forms.ModelForm):
    """Form for processing public contact and booking enquiries."""

    # THE HONEYPOT: Visually hidden from humans using CSS, but bots will fill it out.
    website = forms.CharField(
        required=False,
        label="Leave this field empty",
        widget=forms.TextInput(
            attrs={
                "style": "display:none;",  # Hides it from humans
                "tabindex": "-1",  # Prevents humans from accidentally tabbing into it
                "autocomplete": "off",
            }
        ),
    )

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

    # Custom Django validation to check the honeypot
    def clean_website(self):
        bot_catcher = self.cleaned_data.get("website")
        if bot_catcher:
            # If there is ANY text in this field, it's a bot.
            # Raising a ValidationError stops the form from saving or sending an email.
            raise forms.ValidationError("Automated submission detected.")
        return bot_catcher


class AuditionForm(forms.ModelForm):
    """Form for prospective singers applying to audition."""

    # THE HONEYPOT: Protecting the audition endpoint from automated spam as well.
    website = forms.CharField(
        required=False,
        label="Leave this field empty",
        widget=forms.TextInput(
            attrs={"style": "display:none;", "tabindex": "-1", "autocomplete": "off"}
        ),
    )

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

    # Custom Django validation to check the honeypot
    def clean_website(self):
        bot_catcher = self.cleaned_data.get("website")
        if bot_catcher:
            raise forms.ValidationError("Automated submission detected.")
        return bot_catcher


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


class UserUpdateForm(forms.ModelForm):
    """Allows members to update their core account details."""

    email = forms.EmailField(required=True)  # Forces email to be required

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]


class ProfileUpdateForm(forms.ModelForm):
    """Allows members to update their choir-specific details and legal consents."""

    class Meta:
        model = MemberProfile
        fields = [
            "phone_number",
            "voice_part",
            "emergency_contact_name",
            "emergency_contact_relation",
            "emergency_contact_phone",
            "consent_audio_video",
            "consent_photography",
            "medical_accessibility_notes",
        ]

        # We explicitly tell Django to render the notes field as a larger text box
        widgets = {
            "medical_accessibility_notes": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Optional: Let us know how we can best support you during rehearsals...",
                }
            ),
        }


class CommitteeDocumentForm(forms.ModelForm):
    class Meta:
        model = CommitteeDocument
        fields = ["title", "doc_type", "file"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Document Title"}
            ),
            "doc_type": forms.Select(attrs={"class": "form-control"}),
            "file": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }
