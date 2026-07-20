from django import forms
from django.contrib.auth.models import User

from .models import (
    AuditionApplication,
    AvailabilityPoll,
    ChoirCommunication,
    CommitteeDocument,
    Enquiry,
    Event,
    GiftAidDeclaration,
    MemberProfile,
    Project,
    Repertoire,
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
    """
    Allows members to update their core account details.

    Deliberately excludes email: since ACCOUNT_LOGIN_METHODS = {"email"},
    allauth logs members in against its own EmailAddress records (with
    verification status), not User.email directly. Saving a plain
    ModelForm's email field here updated User.email without ever
    touching EmailAddress, which could leave a member unable to log in
    with the "new" address they'd just set. Email changes now go
    through allauth's own account_email view (see account/email.html),
    which handles verification and keeps User.email in sync correctly.
    """

    class Meta:
        model = User
        fields = ["first_name", "last_name"]


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


class ProjectForm(forms.ModelForm):
    """
    Frontend form for the committee to create/edit a Project - name,
    status (this is where PLANNING -> ACTIVE -> ARCHIVED transitions
    actually happen), dates, and its repertoire list.
    """

    repertoire = forms.ModelMultipleChoiceField(
        queryset=Repertoire.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Project
        fields = ["name", "status", "description", "start_date", "end_date", "repertoire"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g., Christmas 2026"}
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }


class AvailabilityPollForm(forms.ModelForm):
    """Frontend form for the committee to create an availability poll -
    always tied to a PLANNING-phase project, since a poll's whole purpose
    is gauging availability before a project is confirmed as ACTIVE."""

    project = forms.ModelChoiceField(
        queryset=Project.objects.filter(status="PLANNING"),
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = AvailabilityPoll
        fields = ["project", "question", "proposed_date", "notes"]
        widgets = {
            "question": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g., Are you available the weekend of 14-15 March 2027?",
                }
            ),
            "proposed_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
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


class QuickEventScheduleForm(forms.ModelForm):
    """Frontend form allowing committee members to quickly schedule future dates."""

    # Excludes ARCHIVED projects - scheduling a new rehearsal/performance
    # against a closed-out project would be a mistake, not a valid choice.
    # Defaults to whichever project is currently ACTIVE, since that's the
    # overwhelmingly common case (scheduling another date within the
    # project already in progress).
    project = forms.ModelChoiceField(
        queryset=Project.objects.exclude(status="ARCHIVED"),
        initial=Project.get_active,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Event
        # We explicitly expose ONLY the logistical essentials they need to schedule a date
        fields = ["project", "event_type", "date_time", "location"]

        widgets = {
            "event_type": forms.Select(attrs={"class": "form-control"}),
            # This html5 datetime-local input provides a clean pop-up calendar/clock on mobile devices
            "date_time": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
            "location": forms.TextInput(
                attrs={"placeholder": "e.g., St Leonard's Church"}
            ),
        }


class BroadcastForm(forms.ModelForm):
    """Frontend form to allow the committee to send choir-wide communications."""

    class Meta:
        model = ChoirCommunication
        fields = ["audience", "subject", "message"]
        widgets = {
            "subject": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Subject line"}
            ),
            "message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 8,
                    "placeholder": "Enter your update here...",
                }
            ),
        }
