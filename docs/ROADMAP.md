# Roadmap

[Back to README](../README.md)

What I plan to do next, roughly in order. Each item ships the way the October 2026 rebuild did: on its own branch, with tests, additive migrations and a check of the live site afterwards.

## Contents

- [Practice player: sections and Dorico import](#practice-player-sections-and-dorico-import)
- [After the Ewelme project](#after-the-ewelme-project)
- [Smaller improvements](#smaller-improvements)
- [Could have](#could-have)

## Practice player: sections and Dorico import

This is Phase 12 of the rebuild, in three parts that each deploy separately.

1. Sections. The conductor marks named sections of a piece ("Fugue entry, bars 23 to 31"), and singers jump straight to one as a loop. "My note" plays the singer's starting pitch for the section. Sections belong to the piece rather than the track, because every part's track comes from the same Dorico export and shares one timeline. Divided parts (Alto 1 and Alto 2) get a toggle.
2. Dorico import. Uploading the MIDI and MusicXML files exported from Dorico alongside the tracks fills in each bar's timing and each part's starting notes, so sections can be marked by bar number and the lead-in can be a whole bar. The site plays the stored pitch; it never tries to detect notes from the audio.
3. Polish and offline practice, so a singer can keep practising with a weak signal.

## After the Ewelme project

The public Events page has been built from the database since 27 October 2026. The original static page and the switch between the two are still in the code as a fallback. Once the database version has run for a full project cycle, which means after the Ewelme Evensong in March 2027, I will remove the static page, the switch and its setting.

## Smaller improvements

- The About page's mission banner is a large background image and holds the page's mobile performance score at 77. A smaller image, or preloading it, should fix that.
- Re-run the W3C HTML and CSS validators over the rendered Django pages. They were last run on the static site in April 2026.
- A test that every form field has a label, to match the existing tests for tables and inline styles.
- If spam starts reaching the inbox again, add a timing check (reject submissions sent faster than a person could type them) and a limit on links, still without a CAPTCHA.
- Raise HSTS from one hour to a long-lived value once the HTTPS redirect has run without trouble for a while.

## Could have

These are worth doing if there is time, in order of value:

1. A "My attendance" summary on each singer's dashboard.
2. Exporting a term's ledger as a CSV file for the treasurer.
3. A public "Join us" page built around the audition form.
4. A recordings page fed from a recording link on each project.
