# Roadmap

[Back to README](../README.md)

What I plan to do next, roughly in order. Each item ships the way the October 2026 rebuild did: on its own branch, with tests, additive migrations and a check of the live site afterwards.

## Contents

- [Practice player: Dorico import and offline practice](#practice-player-dorico-import-and-offline-practice)
- [After the Ewelme project](#after-the-ewelme-project)
- [Smaller improvements](#smaller-improvements)
- [Could have](#could-have)

## Practice player: Dorico import and offline practice

This is Phase 12 of the rebuild, in three parts that each deploy separately. The first, sections with "My note" and the divided-part toggle, was built on 28 October 2026 (see [Features](FEATURES.md#practice-player)). Two parts remain.

1. Dorico import. Uploading the MIDI and MusicXML files exported from Dorico alongside the tracks fills in each bar's timing and each part's starting notes, so sections can be marked by bar number alone and the lead-in can be a whole bar. Times and notes set by hand are never overwritten. The site plays the stored pitch; it never tries to detect notes from the audio.
2. Polish and offline practice, so a singer can keep practising with a weak signal.

## After the Ewelme project

The public Events page has been built from the database since 27 October 2026. The original static page and the switch between the two are still in the code as a fallback. Once the database version has run for a full project cycle, which means after the Ewelme Evensong in March 2027, I will remove the static page, the switch and its setting.

## Smaller improvements

- Serve the Cinzel and Inter fonts from the site instead of Google Fonts. Since the CSS became one file, Lighthouse's estimate of the first paint on a slow phone is held back by the Google Fonts stylesheet, which needs connections to two more servers before anything shows (see [Testing](TESTING.md#after-the-single-css-file)).
- The About page's mission banner is a large background image, and is the main reason About scores 77 for performance where the other pages score 86 to 90. A smaller image, or preloading it, should close most of that gap.
- A test that every form field has a label, to match the existing tests for tables and inline styles.
- If spam starts reaching the inbox again, add a timing check (reject submissions sent faster than a person could type them) and a limit on links, still without a CAPTCHA.
- Raise HSTS from one hour to a long-lived value once the HTTPS redirect has run without trouble for a while.

## Could have

These are worth doing if there is time, in order of value:

1. A "My attendance" summary on each singer's dashboard.
2. Exporting a term's ledger as a CSV file for the treasurer.
3. A public "Join us" page built around the audition form.
4. A recordings page fed from a recording link on each project.
