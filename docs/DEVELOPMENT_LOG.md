# Development log

[Back to README](../README.md)

How the site was built, stage by stage, with the problems I hit and how I solved them. The commit history has the detail; this is the story behind it.

## Contents

- [Timeline](#timeline)
- [April 2026: the static site](#april-2026-the-static-site)
- [June to August 2026: Django](#june-to-august-2026-moving-to-django)
- [July 2026: the CSS system](#july-2026-the-css-system)
- [October 2026: the rebuild](#october-2026-the-rebuild)
- [Case studies](#case-studies)

## Timeline

| When | Stage |
| --- | --- |
| April 2026 | Strategy, wireframes and a static public site in HTML and CSS, with a prototype members' area |
| June 2026 | The Django application: templates, accounts by invitation, the dashboard, RSVPs, hubs, files on S3, email through Brevo, the first committee tools |
| July 2026 | A test suite, and the CSS rebuilt on LooseLeaf UI with cascade layers and design tokens |
| August 2026 | Gift Aid removed; dashboard tidying |
| September 2026 | Content updates for the Ewelme project |
| October 2026 | A planned rebuild in twelve phases, of which Phases 0 to 11 are done, then validation, accessibility fixes and a single production stylesheet |

## April 2026: the static site

I started with the strategy and wireframes in [UX design](UX_DESIGN.md), then built the four public pages as static HTML with a hand-written CSS file. The layouts used the Every Layout patterns (stack, sidebar, switcher, reel, center), so most of the responsive behaviour came from the patterns rather than from media queries.

The members' area at this stage was a prototype. The login page checked a shared password with an HTML `pattern` attribute, which was a design exercise rather than security, and the dashboard and learning hubs were static pages with placeholder files.

Some of the work from this stage:

- The About page's three video loops, cut in DaVinci Resolve and compressed to under 1 MB each, stacked as sticky slides with a vignette for legible text.
- A scroll-driven animation on the home page using CSS `view-timeline`. It was too new for the W3C validator, and in October I removed it along with the hero's entrance animation, so the home page now shows everything on first paint.
- An accessibility pass: heading order, `datetime` attributes on dates, `aria-describedby` for hints, a square logo file so its width and height attributes no longer distorted it.
- Lighthouse and W3C validation, recorded in [Testing](TESTING.md).

## June to August 2026: moving to Django

In June I turned the static site into a Django application.

- Templates inheriting from one `base.html`.
- Accounts through django-allauth, invite-only through django-invitations, with allauth's pages restyled to match the site.
- Email through Brevo's HTTP API with django-anymail, because Render blocks SMTP.
- Uploaded files on Amazon S3 through django-storages, and static files through WhiteNoise.
- The members' dashboard with RSVPs saved without reloading the page, and signals so every singer has an RSVP for every event (the "auto-healing" RSVPs, which fill any gaps when the dashboard loads).
- Voice-part learning hubs, calendar files and the Document Vault.
- The first committee tools: the subscription ledger, the RSVP report with a member overview, the duty of care roster, document uploads and broadcasts.
- A honeypot on the contact forms.

I also built a Gift Aid declaration feature in June. In August Gift Aid fell out of the choir's scope, so I removed the feature entirely, including its table of declarations, rather than leave unused code and personal data behind.

## July 2026: the CSS system

By July the single stylesheet had grown hard to change safely, so I wrote a regression test suite first and then rebuilt the CSS. The site moved onto LooseLeaf UI, my own small library of CUBE CSS and Every Layout patterns, with native cascade layers and a project-owned `design-tokens.json` for colours, type and spacing. I moved the old styles across in tiers, deleted the selectors nothing used, and fixed the two regressions the move caused. [Architecture](ARCHITECTURE.md#css) describes the result.

In the same period I tied every event to a project, so the dashboard could show overlapping projects as tabs, and fixed two faults in broadcasts. A broadcast to an audience with no matching recipients crashed, and every email went out with the whole recipient list visible to everyone. Broadcasts then went one email per recipient, which kept addresses private but meant many API calls; in October that became a single batch request.

## October 2026: the rebuild

In October I audited the whole site and planned a rebuild in twelve phases. The site was live and in use, so each phase had to be deployable on its own, with additive migrations, tests, and a check of the live site afterwards before the next began.

| Phase | Work | Tests after |
| --- | --- | --- |
| 0. Safety net | HTTPS redirect and HSTS, British English, `scripts/dev.py`, the seed command | 45 at the start |
| 1. Silent fixes | Messages on every page, past events folded away, absolute sharing and canonical URLs, form labels, login errors shown, the hero animation removed | 56 |
| 2. Committee shell | One layout and navigation for the members' area; inline styles and scripts removed; tables that become cards on phones; the honeypot fixed | 68 |
| 3. Events and polls | The committee can edit and delete events, write rehearsal plans, edit and close polls; members can add notes to poll answers | 88 |
| 4. Settings and inbox | Choir Settings replaces values that needed a code change each term; the contact inbox, and then bulk actions for it | 107 |
| 5. Access model | "Committee" separated from Django admin access, and "singer" from "has a login" | 119 |
| 6. Music library | The committee adds pieces and uploads files from the site | 135 |
| 7. Practice player | Waveform, loop, speed without pitch change, note finder, per-track memory | 142 |
| 8. Members and invitations | Inviting, editing and deactivating members on the site | 153 |
| 9. Public events | The Events page built from the schedule, with the old static archive imported as data | 165 |
| 10. Phones first | The public pages reworked for phones | 168 |
| 11. Broadcasts and clean-up | Draft, preview, test, send once with per-recipient records; transition code removed | 184 |

Two follow-ups came from my own use of the site. Setting a loop while a track was already playing did not keep playback inside it, so I made the player check the loop on every frame and renamed "Set A" and "Set B" to "Loop start" and "Loop end". And on phones the committee had to swipe through all 18 navigation links, so the committee tools moved into a drop-down grid. That brought the suite to 186 tests.

After that I re-ran the validators and Lighthouse, which had last been run on the static site in April, and they found more than I expected:

- Date fields on four committee edit pages had been showing up empty. Django wrote dates in the British format and a date input only reads `2026-11-26`, so editing a project, poll, payment or Choir Settings could clear or reject the date.
- The audition form's labels pointed at the enquiry form's fields.
- 25 fields told screen readers to read help text that wasn't on the page.
- The members' area used the brand gold on white, which fails contrast.

Each got a fix and, where it could recur, a test; the [testing page](TESTING.md#bugs-found-and-fixed) lists them all. The same pass removed the RSVP overview's misleading 0% for singers with no replies yet, and renamed the committee's Schedule link to Events, so there are no longer two links called Schedule.

Lighthouse also showed that every page's first paint waited for the stylesheet, which the browser loaded as 52 files, one after another. Production now serves them as one minified file built during each deploy, while the source files stay the ones I edit. Before switching it on I had Chrome compare the two and confirm they produce the same 496 rules in the same layers. My first attempt at the bundle had quietly lost a fifth of the CSS, because an apostrophe in a comment was read as the start of a string, and that comparison is what caught it. The suite is now at 196 tests.

Once the single file was live, Lighthouse's scores moved less than its estimate had promised: home went from 86 to 89, and the other pages barely changed. The real first paint did fall, but Lighthouse scores a simulated slow phone, and there the Google Fonts stylesheet is now what holds the page back. In November I moved the fonts onto the site: four small files and their licences, with the `@font-face` rules inline in the page head and the two Latin files preloaded, so nothing on the first screen waits on another server. That did what the single CSS file alone could not: Lighthouse's simulated first paint fell from 2.9 seconds to about 1, and home, Events, Contact and Login now score 99 or 100 for performance.

### Phase 12, part one: sections

The first part of Phase 12 gave the practice player sections. On a piece's Music Library page the committee marks passages such as "Fugue entry, bars 23 to 31", with a start and end time and each part's starting note. The player sits on the same page, so the times can be set by ear: play the track, pause where the passage starts, and press "Set from player". On a singer's hub, tapping a section loops it from its lead-in, and "My note" plays their starting note for it. Where a part is divided, a toggle swaps between the Alto 1 and Alto 2 tracks without losing the place, because both come from the same Dorico export and share a timeline.

Uploads now read each track's part from its file name, which is how Dorico names them ("Ave verum - Alto 2.mp3"), so a whole set of part tracks goes up in one go. The brief had the form show its guesses and ask for confirmation before saving. Instead it saves straight away and each file has an Edit link for corrections, which is one step fewer when the guesses are right, as they will be for Dorico's names. I also made bar numbers optional on a section, since times alone are enough to loop it, and used up and down buttons rather than drag-to-reorder, which is hard to do accessibly.

Once it was live I wanted sections on individual tracks too, which the brief had ruled out. So a section can now belong to one track instead of the piece, through a Sections link on each track that opens the same editor for that track alone. A track shows the piece's sections and then its own, and a track with different timing, such as a live recording, can stop using the piece's. The suite is now at 224 tests.

### Phase 12, part two: the score import

Typing section times is slow, so the second part lets Dorico do it. I upload the MIDI and MusicXML files Dorico exports with the part tracks, and a section then needs only its bars: the site works out its times, a one-bar lead-in and each part's starting note.

I built it against a real export, Lotti's Crucifixus à 6, which settled two questions. The MusicXML has no record of the final fermata or the ritardando's speed, so the timings have to come from the MIDI's tempo; the MusicXML supplies the bars and the notes. And the first export had the tenor written at treble pitch with an "octave lower" instruction, which would have given tenors a starting note an octave too high; the import now applies the instruction, and handles the octave-treble clef too. I read the MIDI with mido and the MusicXML with Python's own XML parser rather than the large music21 package the brief suggested, and check the audio's length in the committee's player rather than on the server. Anything the committee types by hand is kept through every re-import. Once it was live I wanted more from "My note": a bass who has rested for a few bars needs their next note, not the section's first. The import now keeps every note each part starts, with its time, and "My note" plays the next one from wherever the playhead is, playing or paused. The suite is now at 249 tests.

### The About page

About was the one public page still scoring below 99 for performance. I expected the fix to be a smaller banner photo, but measuring first showed otherwise: the photo was already small, and Lighthouse runs with requests blocked showed the delay came from the poster images of the video slides further down, which a browser fetches with the page however far down they are. They, and the Spotify embed, now load as the visitor scrolls near them. That also keeps Spotify's cookies off the page until then. Seeing the page again afterwards, I decided the slides' looping videos added motion without adding anything to the story, and replaced them with their still frames. Together the two changes took About from 88 to 97 for performance and from 77 to 100 for best practices, and cut what the page downloads on opening from 1,378 KiB to 326. The suite is at 250 tests.

The last part of Phase 12 was to be offline practice. I decided against it for now: it isn't essential, and it belongs with an installable web app I may build once the site has settled. It's on the [roadmap](ROADMAP.md#later-an-installable-web-app) for later.

### Phase 13: a subscription period per project

Our finance officer asked to start a fresh round of subscriptions for each project. The site could already do it, by changing the "current term" on Choir Settings, but it called it a term when the choir thinks in projects, and it sat on a page the finance officer doesn't use. So the word "term" has gone from every screen: singers see "Your subscription for Ewelme 2027", and the finance pages talk about subscription periods. The ledger has a Start new subscription period button that suggests the next project's name, refuses a name that's been used before (it would show that period's payers as already paid), and says what will happen before anything does. While a project is active and subscriptions are still for an older period, the ledger suggests starting one, but nothing ever resets by itself. The database fields kept their old names, which kept this free of migrations. The suite is at 267 tests.

### Phase 14: the Learning Hub as one player

The Gibbons Short Evening Service showed basses two identical "Bass" buttons, one for the Magnificat and one for the Nunc Dimittis, with no way to tell which was which. Looking at why led to a wider rethink of the hub. It had the player at the top and a card per piece under it, each with its own buttons and downloads, so on a phone the player was one feature among many. The hub is now the player. A large drop-down at the top chooses the piece, with its score a button away, and Downloads & links underneath holds the chosen piece's tracks, scores and links. Without JavaScript the page still lists every piece's downloads, each track with a plain audio player.

Where a piece has two tracks for the same part, each now gets a tab named from its file, so the Gibbons reads "Short Mag" and "Short Nunc". A test makes sure no row of buttons ever repeats a label. A field for proper track titles follows in a second deploy, as it needs a migration.

The loop changed most. "Loop off" used to stop at the loop's end anyway, which confused people, so the old button is now a switch with a light and the word On or Off. With the loop off the track simply plays through, and the markers wait until it's switched on again. The markers are A and B flags on the waveform, wide enough to drag on a phone. Two cards under the waveform show each marker's time, and its bar where the score import gives one, with buttons to nudge it half a second or set it to the playhead. In testing I found that tapping a section with the loop off would now have played on past it, so tapping a section also switches the loop on. Downloads also save the file now, rather than opening it in the browser on many phones, through a header the storage link asks for. The suite is at 276 tests.

### Things I learned in the rebuild

The inbox was the most useful thing I built. The day it went live it showed 143 enquiries, every one spam, which had piled up unseen because the honeypot field had never actually been rendered on the page. The forms had always validated it, but bots never saw it. Rendering it and adding bulk delete dealt with both problems.

Testing the live site's own S3 bucket count before and after a test run showed that tests had been uploading files to production since July. Setting `MEDIA_ROOT` in a test does nothing once storage is S3. Tests now use in-memory storage.

Separating "committee" from Django's `is_staff` took two releases on purpose. The first added a Committee group and kept `is_staff` as a fallback, so nobody could be locked out if the migration missed someone. The second removed the fallback once everyone was confirmed in the group.

Free hosting has real limits. Render's free web service has no shell, so I ran the archive import from my own computer against the live database, with `--dry-run` first.

## Case studies

These three problems, from the earlier stages, shaped how I work.

### The 100vh flexbox trap

During early phone testing, pages would not scroll and content spilled out sideways. In Chrome's developer tools I traced it to the `body`, which I had set to `height: 100vh` so the footer would sit at the bottom of short pages. When the switcher layouts stacked their children on a narrow screen they needed more height than that, and with nowhere to grow, the content overflowed sideways instead.

I changed the body to `min-height: 100vh` with `main` set to `flex: 1`. Short pages still fill the screen with the footer at the bottom, and long pages are free to grow, which restored normal scrolling.

### Environment-aware email

Invitations depend on email. Locally I wanted invitation links printed in the terminal so I could click them straight away, but leaving that setting on in production would fail silently: the invitee would never get the email, and nothing would look wrong to the person sending it.

So `settings.py` chooses the backend from `DEBUG`. With `DEBUG=True` email goes to the console. With `DEBUG=False` it goes to Brevo's HTTP API through Anymail, with the API key read from Render's environment. Neither setting needs remembering, and the key never enters the repository.

### Form feedback without JavaScript

I wanted the login form to show whether an email address was valid as the user typed, without adding JavaScript for it. CSS can do it with pseudo-classes: `input:not(:placeholder-shown):invalid` matches only a field that has something typed in it that the browser's own validation rejects, so empty fields stay neutral, invalid ones turn red, and valid ones turn green. The browser's built-in validation does the checking, and CSS only shows the result.
