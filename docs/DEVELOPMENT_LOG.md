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

Phase 12, the rest of the practice player, is on the [roadmap](ROADMAP.md).

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
