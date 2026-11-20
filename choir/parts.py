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
# Short forms used in file names ("... Sop 1.mp3"), read as the full word.
# Not single letters, or "Bar", which could as easily be a bar number.
ABBREVIATIONS = {"sop": "soprano", "sopr": "soprano", "alt": "alto", "ten": "tenor", "bari": "baritone", "bs": "bass"}

# Longest first, so "soprano" is tried before "sop"
_WORDS = "|".join(sorted([*VOICE_WORDS, *ABBREVIATIONS], key=len, reverse=True))
# At the end of a file name's stem, after a non-letter: "Ave verum - Alto 2"
PART_AT_END = re.compile(rf"(?:^|[^a-z])({_WORDS})(?:[\s_-]*(\d{{1,2}}))?\s*$", re.I)
# A whole part name, as the committee types it: "alto 2"
PART_NAME = re.compile(rf"^\s*({_WORDS})(?:\s*(\d{{1,2}}))?\s*$", re.I)

# One pitch in scientific notation: E4, F#4, Bb3 (♯ and ♭ accepted)
PITCH = re.compile(r"^([A-Ga-g])([#♯b♭]?)(\d)$")


def _word(word):
    """The full voice word for a word or its short form: "Sop" -> "soprano"."""
    word = word.lower()
    return ABBREVIATIONS.get(word, word)


def _format(word, number):
    word = _word(word).capitalize()
    return f"{word} {number}" if number else word


def part_from_filename(filename):
    """(voice_part, part_name) read from the end of a file's name, e.g.
    "Ave verum - Alto 2.mp3" -> ("ALT", "Alto 2"); None if it doesn't
    end with a part."""
    stem = filename.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    match = PART_AT_END.search(stem)
    if not match:
        return None
    word, number = match.groups()
    return VOICE_WORDS[_word(word)], _format(word, number)


def normalise_part_name(text):
    """A typed part name tidied ("alto  2" -> "Alto 2"), or None if it
    isn't one."""
    match = PART_NAME.match(text or "")
    return _format(*match.groups()) if match else None


def voice_part_for(part_name):
    """The voice part a part name belongs to ("Alto 2" -> "ALT"), or None."""
    match = PART_NAME.match(part_name or "")
    return VOICE_WORDS[_word(match.group(1))] if match else None


_ANY_PART = re.compile(rf"(?<![a-z])(?:{_WORDS})(?:[\s_-]*\d{{1,2}})?(?![a-z])", re.I)
_SEPARATORS = re.compile(r"[\s\-_–:|,.()]+")


def track_label(asset_name, piece_title="", composer=""):
    """What tells a track apart from the piece's other tracks for the same
    part, when it has no title of its own (Build Order Phase 14a): its
    name without the piece's title, the composer, any part names, a file
    extension and the separators between them. "Gibbons - Short Mag -
    Bass" becomes "Short Mag". Empty if nothing is left."""
    text = re.sub(r"\.(mp3|m4a|wav|pdf)$", "", asset_name or "", flags=re.I)
    for phrase in (piece_title, composer):
        if phrase and phrase.strip():
            text = re.sub(re.escape(phrase.strip()), " ", text, flags=re.I)
    text = _ANY_PART.sub(" ", text)
    text = re.sub(r"(?i)\bfull choir\b", " ", text)
    return _SEPARATORS.sub(" ", text).strip()


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
