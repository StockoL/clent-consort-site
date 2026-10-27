# Testing

[Back to README](../README.md)

How I test the site: an automated suite that runs before every change ships, browser checks driven by script, a manual routine after every deploy, Lighthouse audits, and the bugs this process caught.

## Contents

- [Automated tests](#automated-tests)
- [What the tests cover](#what-the-tests-cover)
- [Browser testing](#browser-testing)
- [The deploy routine](#the-deploy-routine)
- [Lighthouse](#lighthouse)
- [Accessibility](#accessibility)
- [Validation](#validation)
- [Bugs found and fixed](#bugs-found-and-fixed)

## Automated tests

The suite has 186 tests in 46 classes, in `choir/tests.py`. On 27 October 2026 all 186 pass.

```bash
python scripts/dev.py test     # collectstatic, then the whole suite
python scripts/dev.py check    # no missing migrations, then Django's deploy checks
```

`test` collects static files first, because templates look files up in WhiteNoise's manifest and a page that refers to a new script fails until the manifest lists it.

Every new view gets at least three tests: a permission test (anonymous visitors are redirected to login, non-committee members are refused, committee members get the page), a successful POST, and an invalid POST. When the suite was 45 tests I made that the rule, and it is why the suite has grown fourfold.

Tests never touch real services. Email uses Django's in-memory outbox, or Anymail's test backend where I need to check what Brevo would receive. File storage switches to Django's in-memory backend whenever `manage.py test` runs. I added that after finding that tests had been uploading small files to the live S3 bucket for three months (see [bugs](#bugs-found-and-fixed)).

## What the tests cover

| Area | Test classes | Examples of what they prove |
| --- | --- | --- |
| RSVPs | `AttendanceAutoCreationTests`, `DashboardPastEventsTests`, `CommitteeRsvpProjectScopingTests`, `RsvpReportQueryCountTests` | Every singer gets an RSVP for a new event; past events leave the upcoming list; the RSVP report runs a fixed number of queries however much data there is |
| Access | `CommitteePermissionModelTests`, `CommitteeAccessModelTests`, `CommitteeNewUrlPermissionTests`, `NonSingerTests` | Only the Committee group reaches committee pages; `is_staff` alone does not; non-singers get no RSVPs and are left out of the ledger |
| Public pages | `ContactFormTests`, `ContactHoneypotTests`, `PublicEventsPageTests`, `PublicMobilePassTests`, `EventPublicFieldsAndCalendarTests` | Both forms save and email; a filled honeypot is refused; rehearsals and non-public events never reach the Events page; calendar files are valid |
| Members | `MemberRepertoireViewTests`, `HubViewTests`, `PracticePlayerTests`, `AvailabilityPollingTests`, `MemberPollNotesTests`, `DashboardSubnavTests`, `MembersShellTests` | Hubs show only their part's files; the player's JSON lists the right tracks; poll notes save and clear |
| Committee | `CommitteeEventManagementTests`, `CommitteePollEditingTests`, `CommitteeFinancialsTests`, `ChoirSettingsTests`, `CommitteeInboxTests`, `CommitteeInboxBulkTests`, `RepertoireLibraryTests`, `MemberManagementTests`, `MemberInvitationTests`, `CommitteeDocumentDeleteTests`, `CommitteeNavPanelTests` | Payments log against the right term; uploads are checked for type and size; deleting an asset deletes its file; a member cannot remove their own committee access; an invitation can be accepted end to end through allauth |
| Email | `ChoirCommunicationSendTests`, `CommitteeBroadcastTests`, `BroadcastWorkflowTests`, `EmailManagementTests` | A broadcast is sent once only; it goes as one batch so recipients cannot see each other; a test send records nothing; failures are recorded per recipient |
| Site rules | `NoInlineStylesTests`, `TemplateAccessibilityRulesTests`, `PageScriptsTests`, `SiteMessagesTests`, `LoginErrorTests` | No template has an inline style; every data table has a caption and column scope; every `target="_blank"` link has `rel="noopener"`; public pages load only their own scripts |
| Tooling | `SeedDevDataCommandTests`, `EventArchiveImportTests`, `ProjectModelTests` | The seed command refuses to run in production; the archive import can be run twice without duplicating anything |

## Browser testing

Unit tests cannot tell me whether a page fits on a phone or whether the practice player really loops. For that I drive headless Chrome with small Node scripts over the Chrome DevTools protocol, against a local copy of the site with sample data. The scripts set the true viewport size, click, type and press keys as a person would, read values back from the page, and save screenshots.

Headless Chrome will not make a window narrower than 500 pixels, so for true 375-pixel phone views the scripts use device emulation instead of resizing the window.

| Check | What it confirmed |
| --- | --- |
| Public pages at 375, 768 and 1366 pixels, before and after the mobile-first pass | No page scrolls sideways at any width; the home photograph exactly fills the first screen on a phone |
| Phone menu and About videos | The menu opens and closes, a tap on the backdrop cannot reach a link beneath it, and no video downloads on a phone page load |
| Practice player | The waveform draws, speed changes, `[` and `]` set a loop that playback stays inside, and settings return after a reload. Repeated with the audio on a second origin sending no CORS headers, which showed the fallback bar working. |
| Player loop range | Setting a loop while playing, clicking before or after the loop, and pressing Play from outside it all keep playback inside the loop |
| Committee drop-down | The drop-down opens, closes on Escape and outside taps, and shrank the nav strip's overflow from about 1,900 pixels to about 335 |
| User journeys | Every route in [User journeys](USER_JOURNEYS.md), with real form submissions, captured as screenshots |

## The deploy routine

After every deploy I check the live site by hand.

1. As a singer, on my phone: dashboard, change an RSVP, Repertoire, a voice-part hub, open a PDF, Looking Ahead.
2. As a committee member: Committee Hub, Financials, RSVPs, Schedule.
3. Check Render's log for errors.

Only then do I start the next piece of work. Changes that add features get their own check too, such as inviting a test address and signing up with it on the live site.

## Lighthouse

These are Lighthouse 13.5.0 mobile audits of the live site, run after the mobile-first pass on 27 October 2026.

| Page | Performance | Accessibility | Before the pass |
| --- | --- | --- | --- |
| Home | 87 | 100 | 85 / 100 |
| Events | 90 | 100 | 90 / 95 |
| Contact | 91 | 100 | not measured |
| About | 77 | 100 | not measured |

I only trust performance scores from the live site, because my local server does not compress or cache files. About's score is held back by the mission banner's background image, which is the largest element on the page and took 4.9 seconds to paint. A smaller or preloaded image is on the [roadmap](ROADMAP.md).

### April 2026

For comparison, these were the desktop scores of the original static site, before Django.

| Page | Performance | Accessibility | Best practices | SEO |
| --- | --- | --- | --- | --- |
| Home | 98 | 100 | 100 | 100 |
| About | 89 | 95 | 77 | 100 |
| Events | 99 | 95 | 100 | 100 |
| Contact | 99 | 96 | 100 | 100 |
| Members | 100 | 95 | 100 | 100 |

About's best-practices score reflected the embedded Spotify and YouTube players. The original reports are in [images/original](images/original/).

## Accessibility

Lighthouse's accessibility audit scores 100 on all four public pages. To get there I darkened the gold used on white (it failed contrast at 2.3:1), gave the Spotify embed a title and added a hidden `h1` to About. Beyond Lighthouse:

- Tests enforce captions and column scope on every data table.
- Every `label` has a `for` attribute, and groups of checkboxes are fieldsets with a legend. I checked this template by template during the rebuild; it is not yet enforced by a test.
- The honeypot field uses `display: none` rather than a visually-hidden class, so a screen reader user can never land in it and have their message silently refused.

## Validation

I validated the static site's HTML and CSS with the W3C services in April 2026. The HTML issues found (missing `datetime` attributes on dates, an unclosed `main`, headings out of order) were fixed at the time. The CSS validator flagged `view-timeline` and `animation-timeline`, which were newer than the validator; that scroll animation has since been removed.

The Django templates have changed a great deal since, and I have not re-run the W3C validators over the rendered pages yet. That is on the [roadmap](ROADMAP.md). In the meantime, the template rules above are enforced on every test run.

## Bugs found and fixed

These came to light during the October 2026 rebuild, most of them through the tests and browser checks above.

| Bug | Found by | Fix |
| --- | --- | --- |
| The contact page never rendered its honeypot field, so the spam trap had never been on the page. 143 spam enquiries had built up unseen. | Reading the template while restyling it | Both forms render the field, with tests. Bulk delete in the inbox cleared the backlog. |
| Tests were uploading files to the live S3 bucket: 54 had built up since July. | Counting the bucket's objects before and after a test run | Tests use in-memory storage; I deleted the 54 files by exact name and size |
| Saving a user wrote a stale copy of their profile back over newer changes, wiping the voice part an invitation had just set. | The invitation acceptance test | The signal now only creates a missing profile |
| A rehearsal plan containing commas or line breaks produced an invalid calendar file. | Calendar file tests | One calendar builder that escapes text and ends lines as the standard requires |
| The nav strip on phones made the whole page wider than the screen. | Browser check at 375 pixels | `contain: inline-size` on the nav strip |
| Setting a loop while a track was playing did not stop playback leaving the loop. | My own testing on a phone | Playback is checked against the loop on every frame |
| `[` and `]` crashed the player when the key event came from the document itself. | Browser check | Fixed the target check |
| Pressing Practise on the track already loaded reloaded it and restored old settings. | Browser check | Ignored when the track is already loaded |
| Tests failed whenever a template referred to a new script. | The test suite | `staticfiles/` is no longer tracked, and `dev.py test` collects first |
