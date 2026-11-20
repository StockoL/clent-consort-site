# Features

[Back to README](../README.md)

What the site does, page by page. [User journeys](USER_JOURNEYS.md) shows each of these working, and [Committee guide](COMMITTEE_GUIDE.md) explains the committee tools as tasks.

## Contents

- [Public site](#public-site)
- [Accounts and access](#accounts-and-access)
- [Members' area](#members-area)
- [Practice player](#practice-player)
- [Committee tools](#committee-tools)
- [Email](#email)
- [Django admin](#django-admin)

## Public site

### Home

The choir's photograph fills the first screen, with the strapline "Ancient Spires, Modern Voices" and a button to the next project. On phones a short introduction follows, with the next public performance when there is one, and links to About and Events.

### About

How the choir works: its approach, a note from the conductor, and how a project runs from first rehearsal to residency, told over three slides with still photographs behind them, which load as the visitor scrolls near (they were looping videos until November 2026). A Spotify embed gives a sample of the choir's sound, and also loads only as the visitor reaches it.

### Events

The page has three parts:

1. The next public performance, with its venue, date and time ("time TBC" if the committee has not fixed it), a description, and either a ticket link or an Enquire button.
2. Recent performances, each with its programme.
3. The archive, every past performance grouped by year back to 2012. The year headings stay pinned while scrolling on a phone.

All of it is built from the committee's schedule. A performance appears once the committee ticks "Show on the public Events page"; rehearsals never appear. The original static version of the page is still in the code behind a switch in Choir Settings, and will be removed once the database version has run for a full project cycle ([roadmap](ROADMAP.md)).

### Contact

Two forms side by side on a desktop and stacked on a phone: a general or booking enquiry, and an audition application with voice part and experience. Each saves the submission for the committee's inbox and emails the choir's address. Both carry a honeypot: a field hidden from people (with `display: none`, so screen readers skip it too) that bots fill in. A submission with it filled in fails validation, so nothing is saved and no email is sent.

Since November 2026 two more checks sit alongside it, still without a CAPTCHA. Each form carries a hidden, signed note of when the page was shown. A form sent within three seconds of that is refused, and so is one whose note is missing or altered, which means it never came from the page. A real person caught by the timing check is asked to press the button again, and the second press goes through. A page left open for days still sends, since only speed counts. A name containing a web address, or a message or experience box with more than two links, is also refused, with a note saying what to change.

### 404

A branded page with a way back to the home page.

## Accounts and access

Accounts are invite-only, using django-allauth and django-invitations. There is no public sign-up form. A committee member sends an invitation from the Members page, and the invitee sets a password through the link in the email. Email addresses must be verified, and login is by email address.

There are three levels of access, all defined in [`choir/permissions.py`](../choir/permissions.py):

| Level | Who | Sees |
| --- | --- | --- |
| Member | Anyone with an active account | The members' area and the Document Vault |
| Singer | A member with "Is singer" ticked (the default) | Also gets RSVPs for every event, appears in the ledger, polls, rosters and broadcasts |
| Committee | A member of the Committee group, or a superuser | Also gets the committee tools |

Keeping "singer" separate lets the choir give a login to someone who does not sing, such as an accompanist or a trustee, without them being chased for RSVPs or subscriptions.

## Members' area

### Schedule (the dashboard)

- A subscription card when the singer owes for the current subscription period (usually the current project), with the amount, deadline and bank details from Choir Settings, and a payment reference. It disappears once the treasurer logs the payment, and never shows to members who are exempt or not singers.
- A tab per active project, each listing the coming dates as collapsed cards. A card opens to an Attending, Absent or No Response select that saves as soon as it changes, the event type, time and place, an Add to Calendar button, and the rehearsal plan.
- "Add all dates to your calendar" for each project, as a single calendar file.
- Past dates in a folded "Earlier this project" section.

Every singer gets an RSVP for every event automatically. Signals add new singers to future events and add every singer to a new event, and the dashboard fills any gaps when it loads.

### Repertoire and voice-part hubs

Repertoire lists the current projects' pieces and links to each voice part's hub. Each piece's title opens its full score (the PDF) in a new tab, where one has been uploaded. A hub is the practice player, with a drop-down of the project's pieces, and under it Downloads & links: every track, score and recording link for the chosen piece, with its size (for files uploaded since November 2026) and the date it was added. Tracks and scores download rather than open, so they can be kept for practice offline. Without JavaScript the hub lists every piece's downloads, each track with a plain audio player.

### Looking Ahead

Open availability polls for projects still being planned. A member answers Yes, No or Maybe and can add a note, both saved without a submit button.

### Settings

Name, phone number, voice part, emergency contact, consent to recordings and photographs, and medical or accessibility notes. Email addresses are managed through allauth, which verifies a new address before using it.

### Document Vault

Minutes, policies and other documents the committee has uploaded, readable by every member.

## Practice player

The player is most of each voice-part hub. It uses wavesurfer.js, vendored into the repository rather than loaded from a CDN.

- A large drop-down chooses the piece: every piece in the project with anything for the part, in repertoire order. A Score (PDF) button beside it opens the part's own PDF, or else the full score. A link can open a given piece with `?piece=`.
- Where a piece has several tracks for the part (two movements recorded separately, say), tabs above the waveform switch between them, labelled with each track's title ("Magnificat", "Nunc Dimittis"), or from the file names for tracks without one. Part buttons switch between the part's own track, divided lines (Alto 1 and Alto 2) and the full choir. No row of buttons repeats a label.
- A waveform that works as the timeline: click to jump, drag to scrub, inside the loop too.
- Loop markers A and B, drawn as flags on the waveform while the loop is on and dragged to move the loop's ends, and shown as two cards with each one's time and, with the piece's score data, its bar. Each card moves its marker half a second either way, or to the playhead with Set to now; the `[` and `]` keys do the same. Setting a marker switches the loop on. Reset loop puts them back at the ends.
- A Loop switch with an On/Off light. With the loop on, playback stays between the markers and goes back round at B. With it off, the flags are hidden and the track plays straight through; the markers keep their places for when the loop is switched on again.
- A lead-in before marker A when looping: one bar (the bar before, where the piece has score data), two bars, 2 seconds, or off.
- Speed from 50% to 110% without changing the pitch.
- A note finder: an on-screen keyboard that plays any note, for checking a starting note.
- Sections the committee has marked, listed with their bars and length: the piece's, shared by every part's track, and any the track has of its own. Tapping one loops it from its lead-in. If the singer then moves a marker, the section shows as edited, and tapping it again goes back to its marked bars.
- "My note" plays the singer's next note from wherever the playhead is, playing or paused: after a few bars' rest it gives the note they come back in on, and in a section's lead-in the note they enter the section on. That needs the piece's score data; without it, "My note" plays the chosen section's starting note. It plays the note for the track loaded, so Alto 2 hears Alto 2's note.
- Switching between divided lines keeps the place, the loop and the speed, since the tracks share a timeline.
- A bar fixed to the bottom of the screen keeps Play, My note and the Loop switch in reach while scrolling the hub.
- It remembers the last piece, each piece's last track, and each track's position, speed, loop, lead-in and chosen section in the browser's local storage, so a singer picks up where they left off on that device.

If the browser cannot read the audio file to draw a waveform, the player falls back to a plain progress bar and everything else still works.

With a piece's score data uploaded (the MIDI and MusicXML files from Dorico), the committee marks a section by its bars alone, and its times, lead-in and each part's starting note come from the score ([how it works](ARCHITECTURE.md#score-import)).

## Committee tools

| Page | What it does |
| --- | --- |
| Hub | Cards linking to every tool. Non-committee members who reach it see only the Document Vault. |
| Inbox | Enquiries and audition applications, unhandled first. Mark handled (and undo), or select several to mark handled or delete as spam. The nav item shows the unhandled count. |
| Members | Everyone with an account, filterable by voice part and status. Invite by email with optional name and voice part, which are filled in when the invitee signs up. Resend pending invitations. |
| Member edit | Name, voice part, singer, under 18, exempt from subscriptions, committee, active. A committee member cannot remove their own committee access or deactivate themselves. |
| Projects | Create and edit projects (planning, active, archived), their repertoire and their public summary. |
| Music Library | Every piece with its tracks per voice part. Add a piece; upload several PDF, MP3, M4A or WAV files at once (50 MB each), each going to the part its file name ends with, or link to a recording elsewhere. Each file gets a track title, the movement it covers, suggested from its name and editable before uploading ("Gibbons - Short Mag - Bass.mp3" suggests Magnificat), and its size is recorded for Downloads & links. Correct a file's part or title, or take it out of the practice player. Mark the piece's sections, or one track's own, with times set by ear from the player on the page and a starting note per part, or by bars alone once the piece's score data from Dorico is uploaded. Deleting a file removes it from storage too. |
| Events | Coming events by project, with Edit and Delete, and a form for a new event. The edit page has a rich text rehearsal plan and, for performances, the public listing fields. |
| RSVPs | Event Logistics: each event's replies by status, overridable, with an email reminder to everyone who has not answered. Member Overview: each singer's attendance rate over time, lowest first, with "No replies yet" for singers who have not answered anything. |
| Polling | Create, edit, close and reopen availability polls; results with each member's note and a reminder link for those who have not answered. |
| Financials | The subscription ledger for the current subscription period or any earlier one. Log, edit or delete a payment; mark a member exempt. Start a new period for the next project, with a check that its name hasn't been used; when a project is active but subscriptions are still for an older period, the page suggests starting one. |
| Documents | Upload and delete documents for the Document Vault. |
| Broadcast | Write, preview, test and send an email to the whole choir or one voice part. A list of drafts and sent broadcasts with delivery counts. |
| Duty of Care | Emergency contacts, medical notes and under-18 flags for every singer. |
| Choir Settings | Current subscription period, amount and deadline, bank details, social media links, and the Events page switch. Changing the period here works too; earlier payments are kept. |

## Email

Email goes through Brevo's HTTP API using django-anymail, because Render blocks outbound SMTP. Locally, with `DEBUG=True`, it prints to the terminal instead.

Broadcasts are the most careful part. A broadcast is saved as a draft first. The preview page shows the email as it will arrive and the number of recipients. "Send a test to me" sends a copy marked `[Test]` to the sender only. Sending for real needs a ticked confirmation box, checked on the server, as well as a confirm dialog. The broadcast is marked sent before Brevo is called, so a failure part-way through can never cause a second send. All recipients go in one batch request in which each person gets a private copy, so nobody sees anyone else's address. One delivery record per recipient shows whether it went through.

## Django admin

The admin is still available to superusers as a fallback. The site no longer needs it for any routine task. Saving a broadcast in the admin does not send it, and a sent broadcast is read-only there.
