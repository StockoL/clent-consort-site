from django import forms
from django.contrib.auth.models import User
from django.db import models

from .models import (
    AuditionApplication,
    AvailabilityPoll,
    ChoirCommunication,
    ChoirSettings,
    CommitteeDocument,
    Enquiry,
    Event,
    LearningAsset,
    MemberProfile,
    Project,
    Repertoire,
    SubscriptionPayment,
)
from .permissions import COMMITTEE_GROUP


class EnquiryForm(forms.ModelForm):
    """Form for processing public contact and booking enquiries."""

    # THE HONEYPOT: Visually hidden from humans using CSS, but bots will fill it out.
    website = forms.CharField(
        required=False,
        label="Leave this field empty",
        widget=forms.TextInput(
            attrs={
                # Hidden from everyone, screen readers included (see
                # .honeypot in utilities/project-utilities.css)
                "class": "honeypot",
                "id": "enquiry-website",  # both contact forms share one page
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

    def __init__(self, *args, **kwargs):
        # It shares the contact page with EnquiryForm, which has name and
        # email fields too, so its ids get a prefix to stay unique.
        kwargs.setdefault("auto_id", "audition_%s")
        super().__init__(*args, **kwargs)

    # THE HONEYPOT: Protecting the audition endpoint from automated spam as well.
    website = forms.CharField(
        required=False,
        label="Leave this field empty",
        widget=forms.TextInput(
            attrs={
                "class": "honeypot",
                "id": "audition-website",  # both contact forms share one page
                "tabindex": "-1",
                "autocomplete": "off",
            }
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
        fields = ["name", "status", "description", "public_summary", "start_date", "end_date", "repertoire"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g., Christmas 2026"}
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "public_summary": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"),
        }


class RepertoireForm(forms.ModelForm):
    """Add or rename a piece in the committee's repertoire library."""

    class Meta:
        model = Repertoire
        fields = ["composer", "title"]
        widgets = {
            "composer": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Byrd"}),
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Ave verum corpus"}),
        }


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """A file field that accepts several files from one <input multiple>;
    cleans to a list (empty when nothing was chosen)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data if item]
        return [single_clean(data, initial)] if data else []


ASSET_EXTENSIONS = (".pdf", ".mp3", ".m4a", ".wav")
ASSET_MAX_BYTES = 50 * 1024 * 1024  # 50 MB per file


class AssetUploadForm(forms.Form):
    """
    Adds learning assets to one piece: either one or more files (each
    becomes its own asset) or a single external link, never both. With
    several files, each asset is named after its file (minus the
    extension); asset_name is used when exactly one file or a link is
    added, and falls back to the filename when left blank.
    """

    asset_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Soprano practice track"}),
    )
    voice_part = forms.ChoiceField(
        choices=LearningAsset.PART_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    files = MultipleFileField(
        required=False,
        widget=MultipleFileInput(attrs={"accept": ",".join(ASSET_EXTENSIONS)}),
    )
    external_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={"class": "form-control", "placeholder": "https://"}),
    )

    def clean_files(self):
        files = self.cleaned_data["files"]
        for upload in files:
            if not upload.name.lower().endswith(ASSET_EXTENSIONS):
                raise forms.ValidationError(
                    f"{upload.name}: only PDF, MP3, M4A and WAV files can be uploaded."
                )
            if upload.size > ASSET_MAX_BYTES:
                raise forms.ValidationError(
                    f"{upload.name} is over 50 MB. Convert large WAVs to MP3 before uploading."
                )
        return files

    def clean(self):
        cleaned = super().clean()
        files = cleaned.get("files") or []
        url = cleaned.get("external_url")
        if files and url:
            raise forms.ValidationError("Upload files or give a link, not both.")
        if not files and not url and not self.errors:
            raise forms.ValidationError("Choose at least one file to upload, or give a link.")
        if url and not cleaned.get("asset_name"):
            self.add_error("asset_name", "Give the link a name, e.g. 'YouTube recording'.")
        return cleaned

    def save(self, repertoire):
        """Creates and returns the new LearningAsset rows for repertoire."""
        name = self.cleaned_data.get("asset_name", "").strip()
        part = self.cleaned_data["voice_part"]
        files = self.cleaned_data.get("files") or []

        if not files:
            return [
                LearningAsset.objects.create(
                    repertoire=repertoire,
                    voice_part=part,
                    asset_name=name,
                    external_url=self.cleaned_data["external_url"],
                )
            ]

        assets = []
        for upload in files:
            file_name = upload.name.rsplit(".", 1)[0][:150]
            assets.append(
                LearningAsset.objects.create(
                    repertoire=repertoire,
                    voice_part=part,
                    asset_name=name if (name and len(files) == 1) else file_name,
                    file_upload=upload,
                )
            )
        return assets


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
        fields = ["project", "question", "proposed_date", "notes", "is_open"]
        widgets = {
            "question": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g., Are you available the weekend of 14-15 March 2027?",
                }
            ),
            "proposed_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
        labels = {"is_open": "Open for responses"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Keep an existing poll's own project selectable after the project
        # leaves PLANNING, so the poll can still be edited or closed.
        if self.instance.pk:
            self.fields["project"].queryset = Project.objects.filter(
                models.Q(id=self.instance.project_id) | models.Q(status="PLANNING")
            )


class ChoirSettingsForm(forms.ModelForm):
    """The committee Settings page, including the switch (Build Order
    Phase 9) between the old static Events page and the one built from
    public events."""

    class Meta:
        model = ChoirSettings
        fields = [
            "current_term",
            "subscription_amount",
            "subscription_deadline",
            "bank_account_name",
            "bank_sort_code",
            "bank_account_number",
            "youtube_url",
            "instagram_url",
            "facebook_url",
            "events_page_from_db",
        ]
        labels = {
            "youtube_url": "YouTube",
            "instagram_url": "Instagram",
            "facebook_url": "Facebook",
            "events_page_from_db": "Build the public Events page from scheduled events",
        }
        widgets = {
            "current_term": forms.TextInput(attrs={"class": "form-control"}),
            "subscription_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "subscription_deadline": forms.DateInput(attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"),
            "bank_account_name": forms.TextInput(attrs={"class": "form-control"}),
            "bank_sort_code": forms.TextInput(attrs={"class": "form-control", "placeholder": "00-00-00"}),
            "bank_account_number": forms.TextInput(attrs={"class": "form-control", "inputmode": "numeric"}),
            "youtube_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://"}),
            "instagram_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://"}),
            "facebook_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://"}),
        }


class InviteMemberForm(forms.Form):
    """Invite someone to join the members area. Name and voice part are
    optional; when given they're applied to the new member's account as
    they sign up (InvitationProfile, choir.signals.apply_invitation_profile)."""

    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "name@example.com"}))
    first_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    voice_part = forms.ChoiceField(
        choices=[("", "Not known yet")] + MemberProfile.VOICE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def clean_email(self):
        from allauth.account.models import EmailAddress
        from invitations.utils import get_invitation_model

        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists() or EmailAddress.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Someone with this email address already has an account.")
        if get_invitation_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "This address has already been invited. Use Resend in the invitations list instead."
            )
        return email


class MemberEditForm(forms.Form):
    """
    The committee's edit page for one member: names on the User; voice
    part and flags on the MemberProfile; committee via the Committee group;
    active on the User. Email and password stay with the member (allauth).
    The committee can't take committee access away from themselves or
    deactivate themselves - that's how a site gets locked out. Committee
    access is the Committee group alone (choir.permissions.is_committee).
    """

    first_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    voice_part = forms.ChoiceField(
        choices=[("", "Not set")] + MemberProfile.VOICE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    is_singer = forms.BooleanField(required=False, label="Sings with the choir")
    is_under_18 = forms.BooleanField(required=False, label="Under 18")
    is_exempt_from_subs = forms.BooleanField(required=False, label="Exempt from subscriptions")
    committee = forms.BooleanField(required=False, label="Committee member")
    is_active = forms.BooleanField(required=False, label="Active (can log in)")

    def __init__(self, *args, member, editor, **kwargs):
        self.member = member
        self.editor = editor
        profile = member.profile
        kwargs.setdefault(
            "initial",
            {
                "first_name": member.first_name,
                "last_name": member.last_name,
                "voice_part": profile.voice_part or "",
                "is_singer": profile.is_singer,
                "is_under_18": profile.is_under_18,
                "is_exempt_from_subs": profile.is_exempt_from_subs,
                "committee": member.groups.filter(name=COMMITTEE_GROUP).exists(),
                "is_active": member.is_active,
            },
        )
        super().__init__(*args, **kwargs)

    @property
    def editing_self(self):
        return self.member.pk == self.editor.pk

    def clean(self):
        cleaned = super().clean()
        if self.editing_self:
            if not cleaned.get("is_active"):
                self.add_error("is_active", "You can't deactivate your own account.")
            if not cleaned.get("committee") and self.initial.get("committee"):
                self.add_error("committee", "You can't remove your own committee access.")
        return cleaned

    def save(self):
        from django.contrib.auth.models import Group

        member, profile, data = self.member, self.member.profile, self.cleaned_data
        member.first_name = data["first_name"]
        member.last_name = data["last_name"]
        member.is_active = data["is_active"]
        member.save(update_fields=["first_name", "last_name", "is_active"])

        profile.voice_part = data["voice_part"] or None
        profile.is_singer = data["is_singer"]
        profile.is_under_18 = data["is_under_18"]
        profile.is_exempt_from_subs = data["is_exempt_from_subs"]
        profile.save(update_fields=["voice_part", "is_singer", "is_under_18", "is_exempt_from_subs"])

        group, _ = Group.objects.get_or_create(name=COMMITTEE_GROUP)
        if data["committee"]:
            member.groups.add(group)
        else:
            member.groups.remove(group)
        return member


class SubscriptionPaymentForm(forms.ModelForm):
    """
    Replaces committee_financials_view's old raw request.POST.get("amount")
    handling, which had zero validation - a non-numeric amount would 500
    the whole view instead of re-rendering with an error. Excludes member:
    it's stamped programmatically in the view rather than editable through
    the form.
    """

    class Meta:
        model = SubscriptionPayment
        fields = ["amount", "date_paid", "term_reference", "payment_method", "notes"]
        widgets = {
            "amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "date_paid": forms.DateInput(attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"),
            "term_reference": forms.TextInput(attrs={"class": "form-control"}),
            "payment_method": forms.Select(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
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


class EventEditForm(QuickEventScheduleForm):
    """Editing an existing event: the scheduling fields plus the rehearsal
    plan (additional_notes, a TinyMCE HTMLField, so it renders with the
    TinyMCE widget - the template must include {{ form.media }})."""

    class Meta(QuickEventScheduleForm.Meta):
        fields = QuickEventScheduleForm.Meta.fields + [
            "additional_notes",
            # Public listing (Build Order Phase 9); only used for RES events
            "is_public",
            "public_title",
            "public_blurb",
            "ticket_url",
            "end_time",
        ]
        widgets = {
            **QuickEventScheduleForm.Meta.widgets,
            "public_title": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Choral Evensong"}),
            "public_blurb": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "ticket_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://"}),
            "end_time": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}, format="%Y-%m-%dT%H:%M"
            ),
        }
        labels = {"is_public": "Show on the public Events page"}

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("date_time"), cleaned.get("end_time")
        if start and end and end <= start:
            self.add_error("end_time", "The end time must be after the start.")
        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Keep the event's own project selectable even once it's archived,
        # so editing an older event doesn't fail validation.
        if self.instance.pk:
            self.fields["project"].queryset = Project.objects.filter(
                models.Q(id=self.instance.project_id) | ~models.Q(status="ARCHIVED")
            )


class BroadcastForm(forms.ModelForm):
    """Writing or editing a broadcast draft. The message is a TinyMCE
    HTMLField, so it renders with the TinyMCE widget - the template must
    include {{ form.media }}."""

    class Meta:
        model = ChoirCommunication
        fields = ["audience", "subject", "message"]
        widgets = {
            "audience": forms.Select(attrs={"class": "form-control"}),
            "subject": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Subject line"}
            ),
        }
