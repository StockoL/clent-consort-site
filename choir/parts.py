"""
Part names and pitches for the practice player (Learning Hub P2).

My Dorico part names, and the file names Dorico gives each part's track,
follow one pattern: Soprano, Alto, Tenor, Baritone or Bass, optionally
numbered for a divisi line ("Alto 2"). The upload form reads a track's
part from its file name with this, and P3's score import will map the
MusicXML parts the same way.
"""

import re

# Leading word of a part name -> the site's voice part
VOICE_WORDS = {"soprano": "SOP", "alto": "ALT", "tenor": "TEN", "baritone": "BAS", "bass": "BAS"}

_WORDS = "|".join(VOICE_WORDS)
# At the end of a file name's stem, after a non-letter: "Ave verum - Alto 2"
PART_AT_END = re.compile(rf"(?:^|[^a-z])({_WORDS})(?:[\s_-]*(\d{{1,2}}))?\s*$", re.I)
# A whole part name, as the committee types it: "alto 2"
PART_NAME = re.compile(rf"^\s*({_WORDS})(?:\s*(\d{{1,2}}))?\s*$", re.I)

# One pitch in scientific notation: E4, F#4, Bb3 (♯ and ♭ accepted)
PITCH = re.compile(r"^([A-Ga-g])([#♯b♭]?)(\d)$")


def _format(word, number):
    return f"{word.capitalize()} {number}" if number else word.capitalize()


def part_from_filename(filename):
    """(voice_part, part_name) read from the end of a file's name, e.g.
    "Ave verum - Alto 2.mp3" -> ("ALT", "Alto 2"); None if it doesn't
    end with a part."""
    stem = filename.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    match = PART_AT_END.search(stem)
    if not match:
        return None
    word, number = match.groups()
    return VOICE_WORDS[word.lower()], _format(word, number)


def normalise_part_name(text):
    """A typed part name tidied ("alto  2" -> "Alto 2"), or None if it
    isn't one."""
    match = PART_NAME.match(text or "")
    return _format(*match.groups()) if match else None


def voice_part_for(part_name):
    """The voice part a part name belongs to ("Alto 2" -> "ALT"), or None."""
    match = PART_NAME.match(part_name or "")
    return VOICE_WORDS[match.group(1).lower()] if match else None


def normalise_pitches(text):
    """Starting notes as typed ("e4", "F♯4 A4", "bb3, d4") -> the stored
    form, comma-separated with ASCII accidentals ("E4", "F#4,A4",
    "Bb3,D4"). Raises ValueError naming anything that isn't a pitch."""
    pitches = []
    for token in re.split(r"[\s,]+", (text or "").strip()):
        if not token:
            continue
        match = PITCH.match(token)
        if not match:
            raise ValueError(token)
        letter, accidental, octave = match.groups()
        accidental = {"♯": "#", "♭": "b"}.get(accidental, accidental)
        pitches.append(f"{letter.upper()}{accidental}{octave}")
    return ",".join(pitches)
