"""
Score import for the practice player (Learning Hub P3).

The committee uploads two files Dorico exports alongside a piece's part
tracks: the MIDI file and the MusicXML file. From them this works out

- the bar map: when each played bar starts, in seconds, so a section can
  be marked by bar numbers alone. The MusicXML gives the bars (their
  lengths, pickups and repeats); the MIDI gives the tempo, including
  Dorico's ritardandos and fermatas, which the MusicXML leaves out.
- each part's starting pitches in every bar, for "My note". Pitches are
  sounding pitches: a part written at treble pitch with an "octave lower"
  transposition (rather than in the octave-treble clef) is moved down.

Both are stored on the piece (Repertoire.bar_map), so filling a section
needs no file reading. fill_section() then sets a section's times, lead-in
and starting notes from the map. Values the committee set by hand are
never overwritten: only empty times, and times and notes the import set
itself, are (re)filled.

MIDI is read with mido, MusicXML with the standard library's XML parser.
Only the committee can upload these files.
"""

import io
import re
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal

import mido

from .parts import normalise_part_name

STEPS = ["C", "D", "E", "F", "G", "A", "B"]
STEP_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
ACCIDENTALS = {-2: "bb", -1: "b", 0: "", 1: "#", 2: "##"}
DEFAULT_TEMPO = 500000  # microseconds per quarter note (120 bpm), MIDI's default


class ScoreImportError(Exception):
    """A file that can't be read, with a message for the committee."""


# ---------------------------------------------------------------- MIDI


class TempoMap:
    """A MIDI file's tempo changes, to turn a position in quarter notes
    into seconds. end is when the last note finishes, in seconds."""

    def __init__(self, ticks_per_beat, tempos, last_tick):
        self.ticks_per_beat = ticks_per_beat
        self.tempos = tempos  # [(tick, microseconds per quarter)], from tick 0
        self.end = self.seconds_at_tick(last_tick)
        self.end_quarters = last_tick / ticks_per_beat

    def seconds_at_tick(self, target):
        seconds, previous_tick, tempo = 0.0, 0, self.tempos[0][1]
        for tick, new_tempo in self.tempos[1:]:
            if tick >= target:
                break
            seconds += (tick - previous_tick) * tempo / self.ticks_per_beat / 1e6
            previous_tick, tempo = tick, new_tempo
        return seconds + (target - previous_tick) * tempo / self.ticks_per_beat / 1e6

    def seconds_at(self, quarters):
        return self.seconds_at_tick(quarters * self.ticks_per_beat)


def read_midi(data):
    """The tempo map of a Standard MIDI File given as bytes."""
    try:
        midi = mido.MidiFile(file=io.BytesIO(data))
    except Exception as error:  # mido raises several types for bad files
        raise ScoreImportError(f"The MIDI file couldn't be read ({error}).") from error

    tempos, last_tick = [], 0
    for track in midi.tracks:
        tick = 0
        for message in track:
            tick += message.time
            if message.type == "set_tempo":
                tempos.append((tick, message.tempo))
            elif message.type in ("note_on", "note_off"):
                last_tick = max(last_tick, tick)
    if not last_tick:
        raise ScoreImportError("The MIDI file has no notes in it.")
    tempos.sort()
    if not tempos or tempos[0][0] > 0:
        tempos.insert(0, (0, DEFAULT_TEMPO))
    return TempoMap(midi.ticks_per_beat, tempos, last_tick)


# ------------------------------------------------------------ MusicXML


def _musicxml_root(data):
    """The <score-partwise> element of a .musicxml file, or of the score
    inside a compressed .mxl file."""
    if data[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                container = ET.fromstring(archive.read("META-INF/container.xml"))
                rootfile = next(el for el in container.iter() if el.tag.endswith("rootfile"))
                data = archive.read(rootfile.get("full-path"))
        except (zipfile.BadZipFile, KeyError, StopIteration, ET.ParseError) as error:
            raise ScoreImportError("The compressed MusicXML (.mxl) file couldn't be opened.") from error
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise ScoreImportError(f"The MusicXML file couldn't be read ({error}).") from error
    if root.tag != "score-partwise":
        raise ScoreImportError("Export the MusicXML from Dorico as a part-wise score (the default).")
    return root


def _sounding(note, transpose):
    """A pitched <note>'s sounding pitch as (name, midi number), e.g.
    ("Eb4", 63). transpose is the part's (diatonic, chromatic) written to
    sounding shift in force, from its <transpose> element."""
    step = note.findtext("pitch/step")
    alter = round(float(note.findtext("pitch/alter") or 0))
    octave = int(note.findtext("pitch/octave"))
    written = 12 * (octave + 1) + STEP_SEMITONES[step] + alter
    diatonic, chromatic = transpose
    midi = written + chromatic

    index = STEPS.index(step) + diatonic
    step = STEPS[index % 7]
    octave += index // 7
    # If the octave shift sits in the chromatic count only, follow it
    natural = 12 * (octave + 1) + STEP_SEMITONES[step]
    while midi - natural > 6:
        octave += 1
        natural += 12
    while natural - midi > 6:
        octave -= 1
        natural -= 12
    accidental = ACCIDENTALS.get(midi - natural)
    if accidental is None:  # an unusual spelling: fall back to sharps
        names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
        return f"{names[midi % 12]}{midi // 12 - 1}", midi
    return f"{step}{accidental}{octave}", midi


def _transpose(attributes, current):
    element = attributes.find("transpose")
    if element is None:
        return current
    diatonic = int(element.findtext("diatonic") or 0)
    chromatic = int(float(element.findtext("chromatic") or 0))
    octaves = int(element.findtext("octave-change") or 0)
    return diatonic + 7 * octaves, chromatic + 12 * octaves


def read_musicxml(data):
    """The bars and each part's starting pitches from a MusicXML file.

    Returns (measures, parts):
    - measures: one dict per <measure> of the first part, in score order:
      number, length (in quarter notes), and its repeat and ending marks.
    - parts: {part name: [pitches per measure]}, where each entry is the
      sounding pitches at the earliest onset in that measure of a note
      that isn't continuing a tie ("E4", or "E4,G4" for a chord), or ""
      if the part has nothing new there.
    """
    root = _musicxml_root(data)
    names = {sp.get("id"): (sp.findtext("part-name") or "").strip() for sp in root.iter("score-part")}
    part_elements = root.findall("part")
    if not part_elements:
        raise ScoreImportError("The MusicXML file has no parts.")

    measures = []
    parts = {}
    for part_index, part in enumerate(part_elements):
        name = names.get(part.get("id")) or part.get("id")
        divisions, time, transpose = 1, (4, 4), (0, 0)
        starts = []
        for measure in part.findall("measure"):
            attributes = measure.find("attributes")
            if attributes is not None:
                divisions = int(float(attributes.findtext("divisions") or divisions))
                if attributes.find("time/beats") is not None:
                    beats = attributes.findtext("time/beats")
                    # Additive signatures such as 3+2 count as their total
                    time = (sum(int(b) for b in re.findall(r"\d+", beats)), int(attributes.findtext("time/beat-type")))
                transpose = _transpose(attributes, transpose)

            position, furthest, earliest, pitches = 0, 0, None, []
            last_onset = 0
            for element in measure:
                if element.tag == "attributes":
                    divisions = int(float(element.findtext("divisions") or divisions))
                    transpose = _transpose(element, transpose)
                elif element.tag == "backup":
                    position -= int(float(element.findtext("duration") or 0))
                elif element.tag == "forward":
                    position += int(float(element.findtext("duration") or 0))
                    furthest = max(furthest, position)
                elif element.tag == "note":
                    if element.find("grace") is not None or element.find("cue") is not None:
                        continue
                    duration = int(float(element.findtext("duration") or 0))
                    if element.find("chord") is not None:
                        onset = last_onset
                    else:
                        onset = position
                        position += duration
                        last_onset = onset
                    furthest = max(furthest, position)
                    # Tied from the note before (including the middle of a
                    # chain, which is tied both ways): not a new note
                    continuing = any(tie.get("type") == "stop" for tie in element.findall("tie"))
                    if element.find("pitch") is None or continuing:
                        continue
                    pitch = _sounding(element, transpose)
                    if earliest is None or onset < earliest:
                        earliest, pitches = onset, [pitch]
                    elif onset == earliest and pitch not in pitches:
                        pitches.append(pitch)

            starts.append(",".join(name for name, _ in sorted(pitches, key=lambda p: p[1])))
            if part_index == 0:
                content = furthest / divisions
                signature = time[0] * 4 / time[1]
                length = content if measure.get("implicit") == "yes" and content else max(signature, content)
                measures.append({"number": measure.get("number", ""), "length": length, **_repeat_marks(measure)})
        parts[name] = starts
    return measures, parts


def _repeat_marks(measure):
    marks = {"forward": False, "backward": 0, "ending": None, "ending_end": False}
    for barline in measure.findall("barline"):
        repeat = barline.find("repeat")
        if repeat is not None:
            if repeat.get("direction") == "forward":
                marks["forward"] = True
            elif repeat.get("direction") == "backward":
                marks["backward"] = int(repeat.get("times") or 2)
        ending = barline.find("ending")
        if ending is not None:
            if ending.get("type") == "start":
                marks["ending"] = [int(n) for n in re.findall(r"\d+", ending.get("number", ""))]
            if ending.get("type") in ("stop", "discontinue"):
                marks["ending_end"] = True
    return marks


def played_order(measures):
    """The measures in the order they're played, as indexes, following
    repeat barlines and first and second time bars. (Da capo and dal
    segno aren't followed; Dorico's MIDI would then be longer than the
    score, which the import reports.)"""
    order, index, repeat_start, repeat_pass, taken = [], 0, 0, 1, {}
    while index < len(measures):
        measure = measures[index]
        if measure["forward"]:
            repeat_start = index
        if measure["ending"] and repeat_pass not in measure["ending"]:
            # Skip this ending: on to the bar after it closes
            while index < len(measures) and not measures[index]["ending_end"]:
                index += 1
            index += 1
            continue
        order.append(index)
        if measure["ending_end"] and not measure["backward"]:
            # The last time bar of a repeat: it's done, and a later repeat
            # sign goes back no further than the bar after this one
            repeat_pass = 1
            repeat_start = index + 1
        times = measure["backward"]
        if times:
            count = taken.get(index, 0)
            if count < times - 1:
                taken[index] = count + 1
                repeat_pass = count + 2
                index = repeat_start
                continue
            repeat_pass = 1
            repeat_start = index + 1
        index += 1
    return order


# ------------------------------------------------------------- the import


def _bar_number(number):
    return int(number) if str(number).isdigit() else number


def build_bar_map(midi_data, musicxml_data):
    """(bar_map, part_names, report lines) from the two files' bytes.

    bar_map is {"bars": [{"bar", "pass", "start", "notes": {part: pitches}}],
    "end", "midiEnd"}: one entry per played bar, its start in seconds
    from the MIDI's tempo, and each part's new pitches in it."""
    tempo = read_midi(midi_data)
    measures, parts = read_musicxml(musicxml_data)
    order = played_order(measures)

    bars, quarters, seen = [], 0.0, {}
    for index in order:
        number = _bar_number(measures[index]["number"])
        seen[number] = seen.get(number, 0) + 1
        bars.append(
            {
                "bar": number,
                "pass": seen[number],
                "start": round(tempo.seconds_at(quarters), 3),
                "notes": {name: starts[index] for name, starts in parts.items() if starts[index]},
            }
        )
        quarters += measures[index]["length"]
    end = round(tempo.seconds_at(quarters), 3)

    report = [
        f"Tempo map read: {len(bars)} bars played, {format_time(end)} long.",
        f"Parts found: {', '.join(parts)}.",
    ]
    if any(m["backward"] for m in measures):
        report.append("Repeats followed: bars inside them have one entry per time through.")
    # Dorico's MIDI ends when the last note does; the score's bars should
    # account for nearly all of it
    if tempo.end_quarters > quarters + 0.5:
        report.append(
            f"Warning: the MIDI runs {format_time(tempo.end - end)} past the score's last bar. "
            "Check both files come from the same version of the piece (and that it has no D.C. or D.S.)."
        )
    elif quarters - tempo.end_quarters > 2 * measures[order[-1]]["length"]:
        report.append(
            "Warning: the score has more bars than the MIDI has notes for. "
            "Check both files come from the same version of the piece."
        )
    return {"bars": bars, "end": end, "midiEnd": round(tempo.end, 3)}, list(parts), report


def format_time(seconds):
    minutes = int(seconds // 60)
    return f"{minutes}:{seconds - minutes * 60:04.1f}"


def default_part_map(part_names, existing=None):
    """{Dorico part name: site part name} for the parts that are voices
    ("Soprano 1" -> "Soprano 1"; "Organ" -> "", ignored), keeping any
    mapping the committee already chose for a part of the same name."""
    existing = existing or {}
    return {
        name: existing[name] if name in existing else (normalise_part_name(name) or "")
        for name in part_names
    }


def import_score(piece):
    """Reads the piece's uploaded MIDI and MusicXML, stores its bar map,
    part map and report, creates an "Opening" section on first import,
    and fills every section that can be. Raises ScoreImportError."""
    from .models import Section

    if not (piece.score_midi and piece.score_musicxml):
        raise ScoreImportError("Upload both the MIDI and the MusicXML file to import.")
    with piece.score_midi.open("rb") as midi_file:
        midi_data = midi_file.read()
    with piece.score_musicxml.open("rb") as musicxml_file:
        musicxml_data = musicxml_file.read()

    bar_map, part_names, report = build_bar_map(midi_data, musicxml_data)
    first_import = not piece.bar_map
    piece.bar_map = bar_map
    piece.part_map = default_part_map(part_names, piece.part_map)
    mapped = [f"{name} as {site}" for name, site in piece.part_map.items() if site]
    ignored = [name for name, site in piece.part_map.items() if not site]
    report.append(f"Starting notes for: {', '.join(mapped) or 'no parts'}.")
    if ignored:
        report.append(f"Not voice parts, so no starting notes: {', '.join(ignored)}.")
    report.extend(match_track_parts(piece))
    piece.import_log = "\n".join(report)
    piece.save(update_fields=["bar_map", "part_map", "import_log"])

    numbered = [entry["bar"] for entry in bar_map["bars"] if isinstance(entry["bar"], int) and entry["bar"] > 0]
    if first_import and numbered and not piece.sections.filter(asset__isnull=True, bar_start=numbered[0]).exists():
        last = piece.sections.filter(asset__isnull=True).order_by("-order").first()
        Section.objects.create(
            repertoire=piece,
            label="Opening",
            bar_start=numbered[0],
            bar_end=numbered[-1],
            timing_source="IMPORT",
            order=0 if last is None else last.order + 1,
        )
    fill_sections(piece)
    return report


AUDIO_EXTENSIONS = (".mp3", ".m4a", ".wav")


def match_track_parts(piece):
    """Makes the piece's part tracks match the score's parts, so each
    gets its own starting notes. A track with no part name (uploaded
    before names were read from files) gets one from its name, e.g.
    "... Tenor 2", if that's one of the score's parts and in the track's
    voice part. Returns report lines, naming any track that still has no
    matching part (it would get no note, or a wrong one)."""
    from .parts import part_from_filename

    site_parts = {name for name in (piece.part_map or {}).values() if name}
    filled, unmatched = [], []
    for asset in piece.assets.all():
        audio = asset.file_upload and asset.file_upload.name.lower().endswith(AUDIO_EXTENSIONS)
        if not audio or not asset.use_player or asset.voice_part == "ALL":
            continue
        if not asset.part_name:
            guess = part_from_filename(asset.asset_name) or part_from_filename(asset.file_upload.name)
            if guess and guess[0] == asset.voice_part and guess[1] in site_parts:
                asset.part_name = guess[1]
                asset.save(update_fields=["part_name"])
                filled.append(f"{asset.asset_name} as {asset.part_name}")
        if asset.player_part not in site_parts:
            unmatched.append(f"{asset.asset_name} ({asset.player_part})")

    lines = []
    if filled:
        lines.append(f"Part names taken from track names: {', '.join(filled)}.")
    if unmatched:
        lines.append(
            f"Warning: no part in the score matches these tracks, so they get no starting note: {', '.join(unmatched)}. "
            "Set each one's part name with its Edit link under Scores & Tracks, then import again."
        )
    return lines


def fill_sections(piece):
    for section in piece.sections.select_related("asset").prefetch_related("notes"):
        fill_section(section, piece)


def _find(bars, number, after=0, pass_number=None):
    for index in range(after, len(bars)):
        entry = bars[index]
        if entry["bar"] == number and (pass_number is None or entry["pass"] == pass_number):
            return index
    return None


def fill_section(section, piece=None):
    """Sets a section's times, lead-in and starting notes from its piece's
    bar map, if it has bars and the piece has score data. Times are set
    only when empty or set by a previous import; notes likewise, per part.
    A track with its own timing (piece_sections off) is left alone.
    Returns True if anything was set."""
    from .models import SectionNote

    piece = piece or section.repertoire
    bars = (piece.bar_map or {}).get("bars")
    if not bars or section.bar_start is None:
        return False
    if section.asset is not None and not section.asset.piece_sections:
        return False
    first = _find(bars, section.bar_start, pass_number=section.pass_number)
    if first is None:
        return False
    last = _find(bars, section.bar_end, after=first) if section.bar_end is not None else first
    last = first if last is None else last
    offset = Decimal(piece.audio_offset_ms) / 1000
    seconds = lambda value: (Decimal(str(value)) + offset).quantize(Decimal("0.001"))

    changed = False
    if section.timing_source == "IMPORT" or not section.has_times:
        end = bars[last + 1]["start"] if last + 1 < len(bars) else piece.bar_map["end"]
        section.start_seconds = max(Decimal(0), seconds(bars[first]["start"]))
        section.end_seconds = seconds(end)
        # One bar's lead-in: from the start of the bar before
        section.lead_in_seconds = (
            Decimal(str(round(bars[first]["start"] - bars[first - 1]["start"], 3))) if first > 0 else None
        )
        section.timing_source = "IMPORT"
        section.save(update_fields=["start_seconds", "end_seconds", "lead_in_seconds", "timing_source"])
        changed = True

    existing = {note.part_name: note for note in section.notes.all()}
    mapped = set()
    for dorico_name, site_name in (piece.part_map or {}).items():
        if not site_name:
            continue
        if section.asset is not None and section.asset.voice_part != "ALL" and section.asset.player_part != site_name:
            continue  # a track's own section has its own part's note only
        mapped.add(site_name)
        pitches = next((bars[i]["notes"][dorico_name] for i in range(first, last + 1) if dorico_name in bars[i]["notes"]), "")
        note = existing.get(site_name)
        if note is not None and note.source == "MANUAL":
            continue
        if pitches:
            if note is None or note.pitches != pitches:
                SectionNote.objects.update_or_create(
                    section=section, part_name=site_name, defaults={"pitches": pitches, "source": "IMPORT"}
                )
                changed = True
        elif note is not None:
            note.delete()
            changed = True
    # Imported notes for a part no longer mapped (renamed or ignored since)
    for part_name, note in existing.items():
        if note.source == "IMPORT" and part_name not in mapped:
            note.delete()
            changed = True
    return changed
