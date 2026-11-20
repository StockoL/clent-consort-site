# Roadmap

[Back to README](../README.md)

What I plan to do next, roughly in order. Each item ships the way the October 2026 rebuild did: on its own branch, with tests, additive migrations and a check of the live site afterwards.

## Contents

- [Practice player: polish](#practice-player-polish)
- [After the Ewelme project](#after-the-ewelme-project)
- [Smaller improvements](#smaller-improvements)
- [Could have](#could-have)
- [Later: an installable web app](#later-an-installable-web-app)

## Practice player: polish

This is the last part of Phase 12 of the rebuild. Sections with "My note" and the divided-part toggle came first (28 October 2026), then the Dorico import that fills sections in from the score (20 November 2026; see [Features](FEATURES.md#practice-player)). What remains is polish, if singers ask for it:

- Keyboard shortcuts with a help panel, and a two-column layout on desktops.
- A two-bar lead-in option, and a count-in click at the section's tempo.

Offline practice was planned here too. I've moved it to [later](#later-an-installable-web-app): it isn't essential now, and it belongs with an installable app.

## After the Ewelme project

The public Events page has been built from the database since 27 October 2026. The original static page and the switch between the two are still in the code as a fallback. Once the database version has run for a full project cycle, which means after the Ewelme Evensong in March 2027, I will remove the static page, the switch and its setting.

## Smaller improvements

- If spam starts reaching the inbox again, add a timing check (reject submissions sent faster than a person could type them) and a limit on links, still without a CAPTCHA.

## Could have

These are worth doing if there is time, in order of value:

1. A "My attendance" summary on each singer's dashboard.
2. Exporting a term's ledger as a CSV file for the treasurer.
3. A public "Join us" page built around the audition form.
4. A recordings page fed from a recording link on each project.

## Later: an installable web app

Once the site has settled, I'll consider making the members' area an installable web app (a PWA): an icon on the home screen, and the practice player working with no signal, so singers no longer download tracks to play in another app. Some do that now, to practise where there's no signal, and it loses the sections, "My note" and speed control. It isn't essential yet, so it waits.
