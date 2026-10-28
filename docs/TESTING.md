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

The suite has 218 tests in 54 classes, in `choir/tests.py`. On 28 October 2026 all 218 pass.

```bash
python scripts/dev.py test     # build the CSS bundle, collectstatic, then the whole suite
python scripts/dev.py check    # no missing migrations, then Django's deploy checks
```

`test` builds the CSS bundle and collects static files first, because templates look files up in WhiteNoise's manifest and a page that refers to a file the manifest doesn't list fails.

Every new view gets at least three tests: a permission test (anonymous visitors are redirected to login, non-committee members are refused, committee members get the page), a successful POST, and an invalid POST. When the suite was 45 tests I made that the rule, and it is why the suite has grown fourfold.

Tests never touch real services. Email uses Django's in-memory outbox, or Anymail's test backend where I need to check what Brevo would receive. File storage switches to Django's in-memory backend whenever `manage.py test` runs. I added that after finding that tests had been uploading small files to the live S3 bucket for three months (see [bugs](#bugs-found-and-fixed)).

## What the tests cover

| Area | Test classes | Examples of what they prove |
| --- | --- | --- |
| RSVPs | `AttendanceAutoCreationTests`, `DashboardPastEventsTests`, `CommitteeRsvpProjectScopingTests`, `RsvpReportQueryCountTests`, `RsvpOverviewNoRepliesTests` | Every singer gets an RSVP for a new event; past events leave the upcoming list; the RSVP report runs a fixed number of queries however much data there is; a singer with no replies has no rate rather than 0% |
| Access | `CommitteePermissionModelTests`, `CommitteeAccessModelTests`, `CommitteeNewUrlPermissionTests`, `NonSingerTests` | Only the Committee group reaches committee pages; `is_staff` alone does not; non-singers get no RSVPs and are left out of the ledger |
| Public pages | `ContactFormTests`, `ContactHoneypotTests`, `PublicEventsPageTests`, `PublicMobilePassTests`, `EventPublicFieldsAndCalendarTests` | Both forms save and email; a filled honeypot is refused; rehearsals and non-public events never reach the Events page; calendar files are valid |
| Members | `MemberRepertoireViewTests`, `HubViewTests`, `PracticePlayerTests`, `PracticePlayerSectionTests`, `AvailabilityPollingTests`, `MemberPollNotesTests`, `DashboardSubnavTests`, `MembersShellTests` | Hubs show only their part's files; the player's JSON lists the right tracks; a hub gets only shown sections that have times, in order, with only its own part's starting notes; poll notes save and clear |
| Committee | `CommitteeEventManagementTests`, `CommitteePollEditingTests`, `CommitteeFinancialsTests`, `ChoirSettingsTests`, `CommitteeInboxTests`, `CommitteeInboxBulkTests`, `RepertoireLibraryTests`, `MemberManagementTests`, `MemberInvitationTests`, `CommitteeDocumentDeleteTests`, `CommitteeNavPanelTests`, `CommitteeEventsNavLabelTests`, `AssetPartUploadTests`, `PartNameTests` | Payments log against the right term; uploads are checked for type and size; each uploaded track's part is read from its file name; sections reject impossible times, bars and notes; deleting an asset deletes its file; a member cannot remove their own committee access; an invitation can be accepted end to end through allauth |
| Email | `ChoirCommunicationSendTests`, `CommitteeBroadcastTests`, `BroadcastWorkflowTests`, `EmailManagementTests` | A broadcast is sent once only; it goes as one batch so recipients cannot see each other; a test send records nothing; failures are recorded per recipient |
| Site rules | `NoInlineStylesTests`, `TemplateAccessibilityRulesTests`, `PageScriptsTests`, `SiteMessagesTests`, `LoginErrorTests`, `ValidatorFindingsTests`, `HelpTextReferenceTests` | No template has an inline style; every data table has a caption and column scope; every `target="_blank"` link has `rel="noopener"`; public pages load only their own scripts; date fields render in the format browsers accept; the contact page's ids are unique and its labels point at real fields; every `aria-describedby` points at an element on the page |
| Tooling | `SeedDevDataCommandTests`, `EventArchiveImportTests`, `ProjectModelTests`, `CssBundleTests` | The seed command refuses to run in production; the archive import can be run twice without duplicating anything; the CSS bundle keeps every file in its layer and order, its image paths resolve, and production pages link it |

## Browser testing

Unit tests cannot tell me whether a page fits on a phone or whether the practice player really loops. For that I drive headless Chrome with small Node scripts over the Chrome DevTools protocol, against a local copy of the site with sample data. The scripts set the true viewport size, click, type and press keys as a person would, read values back from the page, and save screenshots.

Headless Chrome will not make a window narrower than 500 pixels, so for true 375-pixel phone views the scripts use device emulation instead of resizing the window.

| Check | What it confirmed |
| --- | --- |
| Public pages at 375, 768 and 1366 pixels, before and after the mobile-first pass | No page scrolls sideways at any width; the home photograph exactly fills the first screen on a phone |
| Phone menu and About videos | The menu opens and closes, a tap on the backdrop cannot reach a link beneath it, and no video downloads on a phone page load |
| Practice player | The waveform draws, speed changes, `[` and `]` set a loop that playback stays inside, and settings return after a reload. Repeated with the audio on a second origin sending no CORS headers, which showed the fallback bar working. |
| Player loop range | Setting a loop while playing, clicking before or after the loop, and pressing Play from outside it all keep playback inside the loop |
| Player sections | On an alto hub at 375 pixels: only shown sections are listed; tapping one loops it from its lead-in; moving the loop marks it edited and tapping it restores it; My note plays the right pitches for Alto 1, Alto 2 and a two-note chord; switching from Alto 1 to Alto 2 mid-loop keeps the place, section and loop; a reload restores them. On the committee's piece page: Play loops a hidden section, and Set from player copies the playhead's time into the form. No script errors. |
| Committee drop-down | The drop-down opens, closes on Escape and outside taps, and shrank the nav strip's overflow from about 1,900 pixels to about 335 |
| User journeys | Every route in [User journeys](USER_JOURNEYS.md), with real form submissions, captured as screenshots |

## The deploy routine

After every deploy I check the live site by hand.

1. As a singer, on my phone: dashboard, change an RSVP, Repertoire, a voice-part hub, open a PDF, Looking Ahead.
2. As a committee member: Committee Hub, Financials, RSVPs, Events.
3. Check Render's log for errors.

Only then do I start the next piece of work. Changes that add features get their own check too, such as inviting a test address and signing up with it on the live site.

## Lighthouse

These are Lighthouse 13.5.0 mobile audits of the live site, run on 27 October 2026 against the canonical address (`https://clentconsort.org/`; the `www` address redirects there, which costs about 0.8 seconds and would distort the figures). I ran each page three times. The runs agreed to within a point, and the table shows the median.

| Page | Performance | Accessibility | Best practices | SEO | Largest paint |
| --- | --- | --- | --- | --- | --- |
| Home | 86 | 100 | 100 | 100 | 3.4 s |
| About | 77 | 100 | 77 | 100 | 4.9 s |
| Events | 90 | 100 | 100 | 100 | 2.9 s |
| Contact | 90 | 100 | 100 | 100 | 2.9 s |
| Login | 90 | 100 | 100 | 100 | 2.9 s |

These match the audits I ran after the mobile-first pass earlier the same day (home 87, Events 90, Contact 91, About 77), and improve on the scores before it (home 85 and Events 90 for performance, and Events 95 for accessibility). Lighthouse will not audit the 404 page, because it returns a 404 status.

I only trust performance scores from the live site, because my local server does not compress or cache files.

What holds performance back:

- Render-blocking CSS, on every page. The stylesheet was 52 files joined with `@import`, and the browser only finds each file after loading the one that imports it. Lighthouse estimated that one file would save about 1.9 seconds before the first paint. Production now serves one minified file (see [Architecture](ARCHITECTURE.md#one-file-in-production)), measured below.
- On About, the mission banner's background image, which is the largest element on the page.

About's best-practices score of 77 comes from the embedded YouTube and Spotify players, which set third-party cookies and log browser warnings. I accept that, as I did in April, because the recordings are the best evidence of how the choir sounds.

### After the single CSS file

I ran the same audits on 28 October 2026, once the single file was live, three runs per page with the median shown.

| Page | Performance before | Performance after | Largest paint before | Largest paint after |
| --- | --- | --- | --- | --- |
| Home | 86 | 89 | 3.4 s | 3.0 s |
| About | 77 | 78 | 4.9 s | 4.7 s |
| Events | 90 | 90 | 2.9 s | 2.9 s |
| Contact | 90 | 90 | 2.9 s | 2.9 s |
| Login | 90 | 90 | 2.9 s | 2.9 s |

Accessibility, best practices and SEO are unchanged. The scores moved less than Lighthouse's 1.9-second estimate suggested, and the reason is in the detail. The first paint Lighthouse measured on the actual page load did fall, from 0.73 seconds to 0.45 on Contact. But the score comes from a simulation of a slow phone, and in that simulation the next thing in the way is the Google Fonts stylesheet: before it can arrive, the phone has to connect to two more servers, one for the stylesheet and one for the font files. So the simulated first paint stays at 2.9 seconds. Serving the fonts from the site itself is the next step, and is on the [roadmap](ROADMAP.md#smaller-improvements).

### Members' and committee pages

Those pages need a login, so I audited them for accessibility on the local copy of the site with sample data. Accessibility, unlike performance, does not depend on the server. The first run scored 93 to 97 on every page. The failures were:

- the brand gold (2.3:1 on white) used for page headings, navigation links and outline buttons on light backgrounds;
- a faded "handled" item in the inbox;
- empty phone links on the Duty of Care roster for singers with no emergency number.

After the fixes (see [bugs](#bugs-found-and-fixed)), all 21 pages I audited score 100: the four public pages, six members' pages and eleven committee pages.

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

Lighthouse's accessibility audit scores 100 on every page I audited, public and private. To get there I introduced a darker gold for text on light backgrounds (the brand gold fails contrast at 2.3:1), gave the Spotify embed a title and added a hidden `h1` to About. Beyond Lighthouse:

- Tests enforce captions and column scope on every data table.
- Every `label` has a `for` attribute, and groups of checkboxes are fieldsets with a legend. I checked this template by template during the rebuild; it is not yet enforced by a test.
- The honeypot field uses `display: none` rather than a visually-hidden class, so a screen reader user can never land in it and have their message silently refused.

## Validation

I validated the rendered HTML of 34 pages on 27 October 2026 with the Nu HTML Checker, the validator behind W3C's HTML service. The pages were the seven public pages (including the 404 and password reset), six members' pages and 21 committee pages, among them one of each edit page. Members' and committee pages need a login, so I rendered them from the local copy with sample data and sent the HTML.

W3C's own service started refusing requests part-way through, so I finished the run on validator.nu, which runs the same checker on a separate server. The first pass found real faults, listed under [bugs](#bugs-found-and-fixed): date fields that showed up empty, duplicate ids on the contact page, invalid nesting, broken phone and email links, and 25 fields pointing screen readers at help text that wasn't on the page.

After the fixes, all 34 pages pass with no errors. One report I treat as a false positive: validator.nu does not yet recognise the `fetchpriority` attribute on the home and About pages' image preload. It is part of the HTML standard, and W3C's current checker accepted it. Two kinds of warning remain, both deliberate:

- `role="list"` on unstyled lists. Safari stops announcing a list as a list once its bullets are removed, so the role puts that back. The CSS reset also relies on it.
- `inputmode` on the bank account number in Choir Settings, which tells phones to show a number keypad. It is informational: browsers that ignore it show the normal keyboard.

I validated the CSS with W3C's CSS validator: all 52 source files joined into one upload, with errors traced back to their file and line. It reports one parse error, on the `::part()` selector the practice player uses to style the waveform's loop handles. That selector is part of the CSS Shadow Parts standard and works in every current browser, but the validator does not support it yet. The warnings are the expected kind: custom properties, which it cannot check statically; a few vendor prefixes kept on purpose for scrollbars and iOS; and the older `clip` property in the visually-hidden utility, kept for older browsers.

In April 2026 I validated the original static site the same way. The issues then (missing `datetime` attributes, an unclosed `main`, headings out of order) were fixed at the time.

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
| Date fields on the project, poll, payment and Choir Settings edit pages showed up empty, so saving could clear or reject the date. Django wrote the dates in the British format, which a date input can't read. | W3C HTML validator | Date inputs always render as `2026-11-26`; a test checks it |
| The audition form's Name and Email labels pointed at the enquiry form's fields, because both forms used the same ids. | W3C HTML validator | The audition form's ids have their own prefix; a test checks the page's ids are unique |
| 25 form fields told screen readers to read help text that the page never showed. | Nu HTML Checker | Help text is shown with the right id, or cleared where it only repeated the label; a test checks every reference |
| Phone links on the Duty of Care roster contained spaces, and empty ones were rendered for singers with no emergency number. The reminder email links had unencoded spaces. | W3C HTML validator and Lighthouse | Spaces removed, empty links left out, email links encoded |
| Page headings, navigation links and outline buttons in the members' area used the brand gold on white, at 2.3:1 contrast. | Lighthouse accessibility audit | A darker gold for text on light backgrounds, as a design token |
| Invalid nesting: a heading inside each accordion button, a `div` inside the menu button, and a rehearsal plan's paragraphs inside another paragraph. | W3C HTML validator | Spans styled as before, and a `div` around the plan |
| My first CSS bundle silently dropped about 10 KB of rules: an apostrophe inside a comment was read as the start of a string. | Comparing the bundle's size and rules with the source in Chrome | Comments and strings are read in one pass, as a CSS parser does; a test covers it |
| Pressing Practise on the track already loaded reloaded it and restored old settings. | Browser check | Ignored when the track is already loaded |
| Tests failed whenever a template referred to a new script. | The test suite | `staticfiles/` is no longer tracked, and `dev.py test` collects first |
