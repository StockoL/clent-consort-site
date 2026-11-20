# Roadmap

[Back to README](../README.md)

What I plan to do next, roughly in order. Each item ships the way the October 2026 rebuild did: on its own branch, with tests, additive migrations and a check of the live site afterwards.

## Contents

- [Practice player: offline practice](#practice-player-offline-practice)
- [After the Ewelme project](#after-the-ewelme-project)
- [Smaller improvements](#smaller-improvements)
- [Could have](#could-have)

## Practice player: offline practice

This is the last part of Phase 12 of the rebuild. Sections with "My note" and the divided-part toggle came first (28 October 2026), then the Dorico import that fills sections in from the score (20 November 2026; see [Features](FEATURES.md#practice-player)). What remains is polish and offline practice:

- "Download for rehearsal", so a singer can keep practising a project's tracks in a church hall with no signal.
- Keyboard shortcuts with a help panel, and a two-column layout on desktops.
- A two-bar lead-in option, and a count-in click at the section's tempo if singers ask for it.

## After the Ewelme project

The public Events page has been built from the database since 27 October 2026. The original static page and the switch between the two are still in the code as a fallback. Once the database version has run for a full project cycle, which means after the Ewelme Evensong in March 2027, I will remove the static page, the switch and its setting.

## Smaller improvements

- A test that every form field has a label, to match the existing tests for tables and inline styles.
- If spam starts reaching the inbox again, add a timing check (reject submissions sent faster than a person could type them) and a limit on links, still without a CAPTCHA.
- Raise HSTS from one hour to a long-lived value once the HTTPS redirect has run without trouble for a while.

## Could have

These are worth doing if there is time, in order of value:

1. A "My attendance" summary on each singer's dashboard.
2. Exporting a term's ledger as a CSV file for the treasurer.
3. A public "Join us" page built around the audition form.
4. A recordings page fed from a recording link on each project.
