# Architecture

[Back to README](../README.md)

How the site is built. It is a single Django project with one app, `choir`, served by Gunicorn on Render, with PostgreSQL for data and Amazon S3 for uploaded files.

## Contents

- [Layout of the repository](#layout-of-the-repository)
- [Data model](#data-model)
- [Access model](#access-model)
- [Signals and automatic RSVPs](#signals-and-automatic-rsvps)
- [Templates](#templates)
- [CSS](#css)
- [JavaScript](#javascript)
- [Files and storage](#files-and-storage)
- [Email](#email)
- [Security settings](#security-settings)

## Layout of the repository

| Path | Contents |
| --- | --- |
| `clent_consort_site/` | Project settings and root URLs |
| `choir/models.py` | The data model |
| `choir/views.py`, `choir/urls.py` | Every page and endpoint |
| `choir/forms.py` | Forms, with their widget classes set here rather than in templates |
| `choir/permissions.py` | Who counts as committee and who counts as a singer |
| `choir/signals.py` | Automatic profiles and RSVPs |
| `choir/context_processors.py` | Choir settings, committee flag and inbox count for every template |
| `choir/management/commands/` | `seed_dev_data` and `import_event_archive` |
| `choir/templates/` | Templates, including overrides for allauth and django-invitations |
| `choir/static/css/site/` | The CSS system |
| `choir/static/js/` | Page scripts, plus vendored wavesurfer.js |
| `choir/tests.py` | The test suite |
| `design-tokens.json`, `build-tokens.js` | The source of the colour, type and spacing tokens |
| `scripts/dev.py` | Development commands |
| `build.sh` | Render's build script |

## Data model

| Model | Holds |
| --- | --- |
| `ChoirSettings` | One row: current term, subscription amount and deadline, bank details, social links, and the Events page switch. `ChoirSettings.load()` always returns it. |
| `Project` | A season or residency, with a status (planning, active, archived), dates, repertoire and a public summary |
| `Event` | A rehearsal or performance in a project, with its rehearsal plan and, for performances, the public listing fields |
| `Attendance` | One singer's RSVP for one event |
| `MemberProfile` | One per user: voice part, contact and emergency details, consents, medical notes, and the singer, under-18 and exempt flags |
| `InvitationProfile` | The name and voice part entered when an invitation was sent, copied to the profile on sign-up |
| `SubscriptionPayment` | A payment against a term, with amount, date, method and an optional transaction ID |
| `Repertoire` | A piece: composer and title |
| `LearningAsset` | A score, track or external link for one piece and one voice part (or the full choir) |
| `AvailabilityPoll`, `AvailabilityResponse` | A poll for a planning project, and each member's answer and note |
| `Enquiry`, `AuditionApplication` | Contact form submissions, with handled and handled-by |
| `ChoirCommunication` | A broadcast: audience, subject, message, status (draft or sent) and sent time |
| `BroadcastDelivery` | One row per recipient of a sent broadcast, recording success or the error |
| `CommitteeDocument` | A file in the Document Vault |

Migrations have been additive only since the site went live: new fields have a default or allow null, and data migrations live in their own files, separate from schema changes. Nothing is removed in the same release as the code that stops using it.

## Access model

All the access rules live in [`choir/permissions.py`](../choir/permissions.py), so views, signals, templates and the context processor all get the same answer.

- `is_committee(user)` is true for an active user in the Committee group, or a superuser. Committee views are protected with `@user_passes_test(is_committee)`.
- `is_singer` on the profile decides who gets RSVPs, appears in the ledger, rosters and polls, and receives broadcasts.
- Django's `is_staff` flag only controls admin access. It used to double as "committee", and separating the two took two releases: the first added the group and kept `is_staff` as a fallback, and the second removed the fallback once every committee member was in the group.

Every active member can read the Committee Hub and the Document Vault, because the committee asked for minutes and policies to be open to the whole choir.

## Signals and automatic RSVPs

- A new user gets a `MemberProfile` straight away.
- A new event creates an `Attendance` row for every active singer.
- A new singer gets an `Attendance` row for every future event.
- When an invitation is accepted, the name and voice part from `InvitationProfile` are copied to the profile, without overwriting anything the invitee has filled in.

The dashboard also fills in any missing RSVPs when it loads, which covers a member being made a singer later. The archive import uses `bulk_create`, which skips signals, so historic performances get no RSVPs.

## Templates

`base.html` holds the header, footer, messages and the `scripts` block. Every logged-in page extends `_members_base.html`, which adds the page heading and the members' navigation (`_members_nav.html`). Repeated pieces are partials: `_event_card.html`, `_rsvp_list_item.html`, `_event_fields.html`, `_poll_fields.html` and `_practice_player.html`.

Two rules are enforced by tests that scan every template: no inline `style` attributes (apart from the Spotify embed and the invitation email, where email clients need them), and every data table has a caption and column scope.

## CSS

The CSS is my own system, written in plain CSS with no framework or preprocessor. It follows the CUBE CSS method (composition, utility, block, exception) and uses the composition patterns from Every Layout by Heydon Pickering and Andy Bell. Much of it is vendored from LooseLeaf UI, my own small library of the same patterns.

`choir/static/css/site/index.css` imports every file into native cascade layers, in this order:

```css
@layer reset, global, compositions, blocks, utilities;
```

A later layer always wins over an earlier one, whatever the selector's specificity. So a utility class can always override a block, and specificity fights do not happen.

| Layer | Folder | Examples |
| --- | --- | --- |
| reset | `global/reset.css` | A modern CSS reset |
| global | `global/` | Design tokens, element defaults, the page frame |
| compositions | `compositions/` | `flow`, `cluster`, `sidebar`, `switcher`, `grid`, `reel`, `center`, `wrapper`: layout only, no colour or type |
| blocks | `blocks/` | Components such as `card`, `data-table`, `members-shell`, `practice-player`, `event-listing` |
| utilities | `utilities/` | Single-purpose classes: text sizes, colours, `visually-hidden` |

The compositions do most of the responsive work without media queries. For example, `switcher` puts its children side by side until there is no room, then stacks them; `sidebar` does the same for a fixed-width side panel and a fluid main area. Media queries are kept for a few real changes of layout, such as the members' navigation becoming a sidebar at 60rem and data tables becoming cards below 45rem.

### Design tokens

Colours, the type scale and the spacing scale are defined once in `design-tokens.json`. `node build-tokens.js` turns them into custom properties in `global/variables.css`, the only generated source file, which is committed. Type and space sizes are fluid, using `clamp()` between a phone minimum and a desktop maximum.

```css
--step-0: clamp(1.125rem, 1.0739rem + 0.2273vw, 1.25rem);
```

Some colour tokens change inside dark cards. Any element with `data-variant="invert"` gets a second set of values for the same custom properties, so a component reads `--colors-text-muted` and gets the right grey on either background. Gold text works the same way: `--colors-text-accent` is the darker gold `#8a6d34` on light backgrounds, where the brand gold would fail contrast, and the brand gold inside dark cards.

### Vendored and project files

Files copied from LooseLeaf UI are never edited in place; changes come from re-copying. The site's own additions sit beside them in the same folders, and the comments in `index.css` say which is which.

### One file in production

Locally, pages link `index.css`, and the browser fetches each imported file as it finds it. That is convenient while editing, because a change shows on the next reload. In production that chain of 52 files, each discovered only after the one before it loaded, held back every page's first paint by an estimated 1.9 seconds on a phone.

So production pages link a single file, `site.min.css`, which `scripts/build_css.py` builds from the same sources during each deploy:

- It reads `index.css` and keeps its `@layer` order statement.
- It wraps each imported file in its layer, as `@layer blocks{...}`. The cascade treats that exactly as it treats `@import "x.css" layer(blocks)`.
- It rewrites relative `url()`s so they resolve from the bundle's folder.
- It minifies conservatively, removing comments and whitespace only and leaving quoted strings alone.

The 113 KB of source becomes 54 KB, before WhiteNoise compresses it. The bundle is generated, like `staticfiles/`, and not committed. The `CSS_BUNDLE` setting chooses the file and is on whenever `DEBUG` is off. Before switching it on I checked in Chrome that the bundle and `index.css` produce the same 496 rules in the same layers and order, and that screenshots of eleven pages are identical.

## JavaScript

There is no JavaScript framework. Each page loads only the scripts it needs, through a `scripts` block in `base.html`, and scripts find their elements by `data-` attributes and event delegation rather than inline handlers.

| Script | Used on | Does |
| --- | --- | --- |
| `looseleaf-behaviors.js` | Every page | Accordions and dismissible alerts (vendored) |
| `mobile-menu.js` | Every page | The phone menu and its backdrop |
| `back-to-top.js` | Every page | The back-to-top button |
| `project-carousel.js` | About | The video slides, with reduced-motion and phone handling |
| `member-dashboard.js` | Dashboard, Looking Ahead | Saves RSVPs and poll answers with `fetch` |
| `project-tabs.js` | Dashboard, Repertoire | Project tabs |
| `members-nav.js` | Members' area | Scrolls the phone nav to the current page; the Committee drop-down |
| `practice-player.js` | Voice-part hubs | The practice player |
| `rsvp-dashboard.js` | RSVPs | Tabs, views and RSVP overrides |
| `confirm-forms.js` | Committee pages with delete or send buttons | Asks before destructive actions (`data-confirm`) |
| `select-all.js` | Inbox | The Select all box |

Without JavaScript, every page still shows its content. RSVPs and poll answers need it to save, and the Committee drop-down shows open beneath the nav.

## Files and storage

Static files (CSS, JavaScript, images) are served by WhiteNoise with compressed, hashed file names. `staticfiles/` is not tracked; Render builds it on every deploy.

Uploaded files (scores, tracks, documents) go to a private S3 bucket through django-storages. Links are presigned and last six hours, which is long enough for a practice session. The bucket allows cross-origin reads from the site's own domain only, so the practice player can draw waveforms. Files are never overwritten: a second upload with the same name gets a suffix.

When the tests run, storage switches to Django's in-memory backend, so a test run never touches the real bucket.

## Email

With `DEBUG=False`, email goes through Brevo's HTTP API using django-anymail, because Render blocks outbound SMTP. With `DEBUG=True`, it prints to the terminal. Broadcasts use Anymail's batch sending: setting `merge_data` on the message makes Brevo deliver a private copy to each recipient from a single API call.

## Security settings

With `DEBUG=False` the production settings switch on HTTPS redirects, HSTS (one hour for now) and secure session and CSRF cookies, and read the database URL, secret key and API keys from the environment. Nothing secret is in the repository. `python scripts/dev.py check` runs Django's deploy checks against these settings before any change ships.
