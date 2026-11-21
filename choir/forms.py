import re
import time
from decimal import Decimal

from django import forms
from django.contrib.auth.models import User
from django.core import signing
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
    Section,
    SectionNote,
    SubscriptionPayment,
    format_seconds,
)
from .parts import normalise_part_name, normalise_pitches, part_from_filename, suggest_track_title, voice_part_for
from .permissions import COMMITTEE_GROUP


FORM_STARTED_SALT = "choir.contact-form-started"
FASTEST_HUMAN_SECONDS = 3
MOST_LINKS = 2
LINK = re.compile(r"https?://|www\.", re.IGNORECASE)


class SpamChecks(forms.Form):
    """
    Spam checks for the public contact forms, alongside each form's
    honeypot, still without a CAPTCHA. A form is refused if:

    - it was sent within FASTEST_HUMAN_SECONDS of the page opening. A
      hidden, signed record of when the form was shown (started) gives the
      time; one that's missing or altered means the form was never opened
      in a browser. A person caught by this is asked to press the button
      again, which works because the record keeps its original time.
    - its name has a link in it, or its free text (free_text_field) has
      more than MOST_LINKS links. Both are typical of spam and rare in a
      real enquiry, and the message says how to put it right.

    A page left open for days still works: only being too quick counts.
    """

    free_text_field = None

    started = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["started"].initial = signing.dumps(int(time.time()), salt=FORM_STARTED_SALT)

    def clean_name(self):
        name = self.cleaned_data.get("name", "")
        if LINK.search(name):
            raise forms.ValidationError("Please give just your name here, without a web address.")
        return name

    def clean(self):
        cleaned = super().clean()
        text = cleaned.get(self.free_text_field) or ""
        if len(LINK.findall(text)) > MOST_LINKS:
            self.add_error(
                self.free_text_field,
                f"Please include no more than {MOST_LINKS} links. We'll ask for anything else we need.",
            )
        try:
            started = signing.loads(cleaned.get("started") or "", salt=FORM_STARTED_SALT)
        except signing.BadSignature:
            raise forms.ValidationError("This form couldn't be sent. Please reload the page and try again.")
        if time.time() - started < FASTEST_HUMAN_SECONDS:
            raise forms.ValidationError(
                "That was sent so quickly it looked automated. Please check your details and press the button again."
            )
        return cleaned


class EnquiryForm(SpamChecks, forms.ModelForm):
    """Form for processing public contact and booking enquiries."""

    free_text_field = "message"

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


class AuditionForm(SpamChecks, forms.ModelForm):
    """Form for prospective singers applying to audition."""

    free_text_field = "experience"

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

    # These fields' help texts are the wording members agree to, so the page
    # shows them as the labels; as help texts too, screen readers would read
    # them twice.
    HELP_AS_LABEL = ("consent_audio_video", "consent_photography", "medical_accessibility_notes")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.HELP_AS_LABEL:
            self.fields[name].label = self.fields[name].help_text
            self.fields[name].help_text = ""

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
        # Repeats the label or placeholder, so not shown on the page.
        help_texts = {"name": ""}
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

    Each file's part is read from the end of its name, as Dorico writes it
    ("Ave verum - Alto 2.mp3", choir.parts). With "From each file's name"
    that sets the voice part too, so a whole set of part tracks uploads in
    one go; a chosen voice part wins, and keeps the part name only where
    the file's agrees with it.

    Each file's track title (Build Order Phase 14b) is the title typed for
    it on the page (file_title_<n>, for the nth file, which the page's
    script adds with suggestions filled in), else the one Track title for
    every file, else the suggestion from its name (suggest_track_title).
    """

    TITLE_MAX = 60

    asset_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Soprano practice track"}),
    )
    voice_part = forms.ChoiceField(
        choices=[("", "From each file's name")] + LearningAsset.PART_CHOICES,
        required=False,
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
    track_title = forms.CharField(
        max_length=TITLE_MAX,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Magnificat"}),
    )

    def file_titles(self, files):
        """Each file's title as typed on the page, or None where the page
        sent none (no script)."""
        return [
            self.data[f"file_title_{n}"].strip() if f"file_title_{n}" in self.data else None
            for n in range(len(files))
        ]

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
        too_long = [
            upload.name
            for upload, title in zip(files, self.file_titles(files))
            if title and len(title) > self.TITLE_MAX
        ]
        if too_long:
            self.add_error(
                "track_title",
                f"Keep track titles to {self.TITLE_MAX} characters ({', '.join(too_long)}).",
            )
        if url and not cleaned.get("asset_name"):
            self.add_error("asset_name", "Give the link a name, e.g. 'YouTube recording'.")
        if not cleaned.get("voice_part"):
            if url:
                self.add_error("voice_part", "Choose the voice part this link is for.")
            unknown = [upload.name for upload in files if not part_from_filename(upload.name)]
            if unknown:
                self.add_error(
                    "voice_part",
                    f"I can't tell the voice part from {', '.join(unknown)}. Choose one above, "
                    "or rename the file to end with its part (e.g. '... Alto 2.mp3').",
                )
        return cleaned

    def save(self, repertoire):
        """Creates and returns the new LearningAsset rows for repertoire."""
        name = self.cleaned_data.get("asset_name", "").strip()
        chosen = self.cleaned_data["voice_part"]
        files = self.cleaned_data.get("files") or []

        if not files:
            return [
                LearningAsset.objects.create(
                    repertoire=repertoire,
                    voice_part=chosen,
                    asset_name=name,
                    external_url=self.cleaned_data["external_url"],
                    use_player=False,
                )
            ]

        shared_title = self.cleaned_data.get("track_title", "").strip()
        assets = []
        for upload, typed_title in zip(files, self.file_titles(files)):
            file_name = upload.name.rsplit(".", 1)[0][:150]
            detected_part, detected_name = part_from_filename(upload.name) or (None, "")
            part = chosen or detected_part
            if typed_title is not None:
                title = typed_title
            else:
                title = shared_title or suggest_track_title(upload.name, repertoire.title, repertoire.composer)
            assets.append(
                LearningAsset.objects.create(
                    repertoire=repertoire,
                    voice_part=part,
                    part_name=detected_name if detected_part == part else "",
                    asset_name=name if (name and len(files) == 1) else file_name,
                    track_title=title[: self.TITLE_MAX],
                    file_size=upload.size,
                    file_upload=upload,
                )
            )
        return assets


class AssetEditForm(forms.ModelForm):
    """Corrects one asset on the piece page: its name, voice part, part
    name ("Alto 2", for a divisi line), whether it opens in the practice
    player, and whether the piece's sections apply to it as well as its
    own. Rendered once per asset, so each has a prefix."""

    class Meta:
        model = LearningAsset
        fields = ["asset_name", "voice_part", "part_name", "track_title", "use_player", "piece_sections"]
        labels = {
            "asset_name": "Name",
            "track_title": "Track title",
            "use_player": "Open in the practice player",
            "piece_sections": "Use the piece's sections (untick for a track with different timing)",
        }
        help_texts = {
            "asset_name": "",
            "track_title": "Name the movement this track covers, such as Magnificat, when a piece has more "
            "than one. Leave blank if the track is the whole piece.",
        }
        widgets = {
            "asset_name": forms.TextInput(attrs={"class": "form-control"}),
            "voice_part": forms.Select(attrs={"class": "form-control"}),
            "part_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Alto 2"}),
            "track_title": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Magnificat"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The hint under the field, which the template gives this id
        self.fields["track_title"].widget.attrs["aria-describedby"] = f"{self['track_title'].auto_id}-hint"

    def clean_part_name(self):
        text = self.cleaned_data["part_name"].strip()
        if not text:
            return ""
        part_name = normalise_part_name(text)
        if not part_name:
            raise forms.ValidationError("Use a part name like 'Alto' or 'Alto 2'.")
        return part_name

    def clean(self):
        cleaned = super().clean()
        part_name = cleaned.get("part_name")
        voice_part = cleaned.get("voice_part")
        if part_name and voice_part and voice_part_for(part_name) != voice_part:
            self.add_error(
                "part_name",
                f"'{part_name}' doesn't belong to {dict(LearningAsset.PART_CHOICES)[voice_part]}. "
                "Change the voice part, or clear the part name.",
            )
        return cleaned


class SecondsField(forms.CharField):
    """A time in a track, typed as m:ss ("1:04.2") or plain seconds
    ("64.2"); cleans to a Decimal of seconds, or None when blank."""

    TIME = re.compile(r"^(?:(\d+):)?(\d+(?:\.\d+)?)$")

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault(
            "widget",
            forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal", "placeholder": "m:ss"}),
        )
        super().__init__(**kwargs)

    def prepare_value(self, value):
        return value if isinstance(value, str) else format_seconds(value)

    def to_python(self, value):
        value = super().to_python(value).strip()
        if not value:
            return None
        match = self.TIME.match(value)
        if not match:
            raise forms.ValidationError("Give a time like 1:04.2, or in seconds.")
        minutes, seconds = match.groups()
        seconds = Decimal(seconds)
        if minutes is not None and seconds >= 60:
            raise forms.ValidationError("Seconds after the colon must be under 60.")
        return (Decimal(minutes or 0) * 60 + seconds).quantize(Decimal("0.001"))


class SectionForm(forms.ModelForm):
    """
    Adds or edits one section of a piece (Learning Hub P2): its label,
    bars, start and end times, and a starting note per part. part_names
    are the piece's parts ("Soprano", "Alto 1", ...), one note field each;
    a part left blank has no "My note" for that section.
    """

    start_seconds = SecondsField(label="Start")
    end_seconds = SecondsField(label="End")

    class Meta:
        model = Section
        fields = ["label", "bar_start", "bar_end", "start_seconds", "end_seconds", "published"]
        labels = {
            "bar_start": "First bar",
            "bar_end": "Last bar",
            "published": "Show to members",
        }
        widgets = {
            "label": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Fugue entry"}),
            "bar_start": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "bar_end": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
        }

    def __init__(self, *args, part_names=(), **kwargs):
        kwargs.setdefault("auto_id", "section_%s")
        super().__init__(*args, **kwargs)
        existing = {}
        if self.instance.pk:
            existing = {note.part_name: note.pitches for note in self.instance.notes.all()}
        # Parts the piece has, then any a note already exists for
        names = list(part_names) + [name for name in existing if name not in part_names]
        self.note_fields = []
        for index, part_name in enumerate(names):
            field_name = f"note_{index}"
            self.fields[field_name] = forms.CharField(
                label=part_name,
                required=False,
                max_length=50,
                initial=existing.get(part_name, "").replace(",", ", "),
                widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., E4"}),
            )
            self.note_fields.append((field_name, part_name))

    def notes(self):
        """The note fields as bound fields, for the template."""
        return [self[field_name] for field_name, _ in self.note_fields]

    def clean(self):
        cleaned = super().clean()
        bar_start, bar_end = cleaned.get("bar_start"), cleaned.get("bar_end")
        if bar_end is not None and bar_start is None:
            self.add_error("bar_start", "Give the first bar too.")
        elif bar_start is not None and bar_end is not None and bar_end < bar_start:
            self.add_error("bar_end", "The last bar can't come before the first.")
        start, end = cleaned.get("start_seconds"), cleaned.get("end_seconds")
        if start is not None and end is not None and end <= start:
            self.add_error("end_seconds", "The end must come after the start.")
        for field_name, _ in self.note_fields:
            try:
                cleaned[field_name] = normalise_pitches(cleaned.get(field_name))
            except ValueError as error:
                self.add_error(field_name, f"'{error}' isn't a note. Use names like E4, F#4 or Bb3.")
        return cleaned

    def save(self, commit=True):
        # Times set by hand are never overwritten by a score import (P3).
        # Cleared times go back to the import, which refills them from
        # the bars; changed bars on an imported section are recomputed.
        if {"start_seconds", "end_seconds"} & set(self.changed_data):
            self.instance.timing_source = "MANUAL"
        section = super().save(commit=commit)
        if commit:
            existing = {note.part_name: note for note in section.notes.all()}
            for field_name, part_name in self.note_fields:
                pitches = self.cleaned_data.get(field_name)
                note = existing.get(part_name)
                if note is not None and note.pitches == pitches:
                    continue  # unchanged: keeps its source (an imported note stays imported)
                if pitches:
                    SectionNote.objects.update_or_create(
                        section=section,
                        part_name=part_name,
                        defaults={"pitches": pitches, "source": "MANUAL"},
                    )
                elif note is not None:
                    note.delete()
        return section


SCORE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB; a long anthem's MusicXML is well under 1 MB


class ScoreDataForm(forms.ModelForm):
    """A piece's score data (Learning Hub P3): the MIDI and MusicXML files
    Dorico exports with the part tracks, and the audio offset. Either file
    can be replaced on its own; the import runs once both are there."""

    class Meta:
        model = Repertoire
        fields = ["score_midi", "score_musicxml", "audio_offset_ms"]
        labels = {
            "score_midi": "MIDI file",
            "score_musicxml": "MusicXML file",
            "audio_offset_ms": "Audio offset (milliseconds)",
        }
        widgets = {
            "score_midi": forms.FileInput(attrs={"accept": ".mid,.midi"}),
            "score_musicxml": forms.FileInput(attrs={"accept": ".musicxml,.xml,.mxl"}),
            "audio_offset_ms": forms.NumberInput(attrs={"class": "form-control", "step": 10}),
        }

    def _check(self, name, extensions, kind):
        upload = self.cleaned_data.get(name)
        if upload and hasattr(upload, "size"):  # a new file, not the stored one
            if not upload.name.lower().endswith(extensions):
                raise forms.ValidationError(f"{upload.name} isn't a {kind} file.")
            if upload.size > SCORE_MAX_BYTES:
                raise forms.ValidationError(f"{upload.name} is over 5 MB.")
        return upload

    def clean_score_midi(self):
        return self._check("score_midi", (".mid", ".midi"), "MIDI")

    def clean_score_musicxml(self):
        return self._check("score_musicxml", (".musicxml", ".xml", ".mxl"), "MusicXML")


class PartMapForm(forms.Form):
    """Which site part each Dorico part's starting notes belong to. Filled
    in by the import from the part names; a part left blank (an organ,
    say) gets no starting notes."""

    def __init__(self, *args, part_map=None, **kwargs):
        kwargs.setdefault("auto_id", "partmap_%s")
        super().__init__(*args, **kwargs)
        self.parts = []
        for index, (dorico_name, site_name) in enumerate((part_map or {}).items()):
            field_name = f"part_{index}"
            self.fields[field_name] = forms.CharField(
                label=dorico_name,
                required=False,
                max_length=40,
                initial=site_name,
                widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Not a voice part"}),
            )
            self.parts.append((field_name, dorico_name))

    def clean(self):
        cleaned = super().clean()
        for field_name, _ in self.parts:
            text = (cleaned.get(field_name) or "").strip()
            if text:
                part_name = normalise_part_name(text)
                if not part_name:
                    self.add_error(field_name, "Use a part name like 'Alto' or 'Tenor 2', or leave it blank.")
                else:
                    cleaned[field_name] = part_name
            else:
                cleaned[field_name] = ""
        return cleaned

    def part_fields(self):
        """The fields as bound fields, for the template."""
        return [self[field_name] for field_name, _ in self.parts]

    def part_map(self):
        return {dorico_name: self.cleaned_data[field_name] for field_name, dorico_name in self.parts}


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
        # Repeats the label or placeholder, so not shown on the page.
        help_texts = {"question": ""}
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
        # Repeats the label or placeholder, so not shown on the page.
        # current_term is the subscription period (Build Order Phase 13).
        help_texts = {
            "subscription_amount": "",
            "current_term": "e.g., Ewelme 2027. Payments are logged against this.",
        }
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
    # Inviting a parent for an under-18 singer (Build Order Phase 15): set
    # from the singer's page, and linked as they sign up
    guardian_of = forms.ModelChoiceField(
        queryset=MemberProfile.objects.filter(is_under_18=True), required=False, widget=forms.HiddenInput
    )

    def clean_email(self):
        return check_new_email(self.cleaned_data["email"])


def check_new_email(email):
    """An address that can be invited: nobody has it, and it hasn't
    been invited already."""
    from allauth.account.models import EmailAddress
    from invitations.utils import get_invitation_model

    email = email.strip()
    if User.objects.filter(email__iexact=email).exists() or EmailAddress.objects.filter(email__iexact=email).exists():
        raise forms.ValidationError("Someone with this email address already has an account.")
    if get_invitation_model().objects.filter(email__iexact=email).exists():
        raise forms.ValidationError(
            "This address has already been invited. Use Resend in the invitations list instead."
        )
    return email


def possible_guardians(exclude=None):
    """Members who can be linked as a parent or guardian: active, with a
    login of their own (so not another child without one), by name."""
    users = User.objects.filter(is_active=True).exclude(password__startswith="!")
    if exclude is not None:
        users = users.exclude(pk=exclude.pk)
    return users.order_by("first_name", "last_name", "username")


class _MemberLabels:
    """Members listed by name, with their email to tell two apart."""

    def label_from_instance(self, user):
        name = user.get_full_name() or user.username
        return f"{name} ({user.email})" if user.email else name


class MemberChoiceField(_MemberLabels, forms.ModelChoiceField):
    pass


class MembersChoiceField(_MemberLabels, forms.ModelMultipleChoiceField):
    pass


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
    # Build Order Phase 15: shown for an under-18 singer, or anyone who
    # still has a parent linked
    guardians = MembersChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Parents or guardians",
        widget=forms.SelectMultiple(attrs={"class": "form-control", "size": 6, "aria-describedby": "guardians-hint"}),
    )

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
                "guardians": list(profile.guardians.all()),
            },
        )
        super().__init__(*args, **kwargs)
        self.fields["guardians"].queryset = possible_guardians(exclude=member)

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
        profile.guardians.set(data["guardians"])

        group, _ = Group.objects.get_or_create(name=COMMITTEE_GROUP)
        if data["committee"]:
            member.groups.add(group)
        else:
            member.groups.remove(group)
        return member


class AddUnder18Form(forms.Form):
    """Adds an under-18 singer (Build Order Phase 15): their name and
    voice part, and their parent or guardian, either a member already or
    someone to invite by email. The child gets no login of their own."""

    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"class": "form-control"}))
    voice_part = forms.ChoiceField(choices=MemberProfile.VOICE_CHOICES, widget=forms.Select(attrs={"class": "form-control"}))
    parent = MemberChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="Not a member yet: invite them below",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    parent_email = forms.EmailField(
        required=False, widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "name@example.com"})
    )
    parent_first_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    parent_last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={"class": "form-control"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parent"].queryset = possible_guardians()

    def clean_parent_email(self):
        email = self.cleaned_data["parent_email"]
        return check_new_email(email) if email else ""

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        if cleaned.get("parent") and cleaned.get("parent_email"):
            raise forms.ValidationError("Choose the parent from the members list or give an email address to invite, not both.")
        if not cleaned.get("parent") and not cleaned.get("parent_email"):
            raise forms.ValidationError(
                "Choose their parent or guardian, or give an email address to invite them. "
                "The choir contacts them, not the singer."
            )
        return cleaned


class SplitMemberForm(forms.Form):
    """The child's name, when splitting a parent's account that stood in
    for them (Build Order Phase 15, choir.guardians.split_parent_record)."""

    first_name = forms.CharField(
        max_length=150, label="Child's first name", widget=forms.TextInput(attrs={"class": "form-control"})
    )
    last_name = forms.CharField(
        max_length=150, label="Child's last name", widget=forms.TextInput(attrs={"class": "form-control"})
    )


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
        # The choir thinks in projects, not terms (Build Order Phase 13); the
        # field keeps its name, since renaming it would mean a migration
        labels = {"term_reference": "Subscription period"}
        help_texts = {"term_reference": "e.g., Ewelme 2027"}
        widgets = {
            "amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "date_paid": forms.DateInput(attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"),
            "term_reference": forms.TextInput(attrs={"class": "form-control"}),
            "payment_method": forms.Select(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class SubscriptionPeriodForm(forms.Form):
    """
    Starts a new subscription period from the ledger (Build Order Phase
    13): its name (usually the project's, "Ewelme 2027"), amount and
    optional deadline, which replace ChoirSettings' current_term,
    subscription_amount and subscription_deadline.

    The name must be new. Reusing the current period's name would change
    nothing, and reusing an earlier one would show that period's payers as
    already paid. used_names is every name payments have been logged
    against, plus the current one.
    """

    name = forms.CharField(
        max_length=100,
        label="Name",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Ewelme 2027"}),
    )
    amount = forms.DecimalField(
        max_digits=6,
        decimal_places=2,
        min_value=0,
        label="Amount (£)",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
    deadline = forms.DateField(
        required=False,
        label="Pay by (optional)",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"),
    )

    def __init__(self, *args, current_name="", used_names=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.current_name = current_name
        self.used_names = {name.strip().lower() for name in used_names if name}

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Give the new period a name, such as the project's.")
        if name.lower() == self.current_name.strip().lower():
            raise forms.ValidationError(f"Subscriptions are already for {name}. Choose a new name.")
        if name.lower() in self.used_names:
            raise forms.ValidationError(
                f"Payments have already been logged for {name}, so those members would show as paid. "
                "Choose a new name, for example by adding the year."
            )
        return name


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
        # The label already says it, so the help text is not shown.
        help_texts = {"is_public": ""}

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
        # Repeats the label or placeholder, so not shown on the page.
        help_texts = {"message": ""}
        fields = ["audience", "subject", "message"]
        widgets = {
            "audience": forms.Select(attrs={"class": "form-control"}),
            "subject": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Subject line"}
            ),
        }
