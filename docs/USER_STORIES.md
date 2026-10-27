# User stories

[Back to README](../README.md)

The site serves five kinds of people. I wrote their stories first, with acceptance criteria in Given/When/Then form, and used MoSCoW to decide what to build first. The table at the end shows each story's priority and where it stands now. [User journeys](USER_JOURNEYS.md) has screenshots of each story working.

## Contents

- [Priorities](#priorities)
- [The people](#the-people)
- [Cathedral and church staff](#cathedral-and-church-staff)
- [The public](#the-public)
- [Singers](#singers)
- [The committee](#the-committee)
- [Maintainer](#maintainer)
- [MoSCoW and status](#moscow-and-status)
- [Won't have, for now](#wont-have-for-now)

## Priorities

| Priority | Meaning |
| --- | --- |
| Must have | The site fails its purpose without it. |
| Should have | Important, and expected soon after launch. |
| Could have | Valuable when there is time. |
| Won't have (for now) | Deliberately left out, with the reason given. |

## The people

| Code | Who | What they come for |
| --- | --- | --- |
| C | Cathedral and church staff: deans, precentors, directors of music | Deciding whether to host the choir for a weekend residency |
| P | The public | Concert-goers, and singers thinking of joining |
| S | Singers | Their schedule, their music and choir admin |
| K | The committee | Running the choir |
| M | Me, as the maintainer | Changing the site safely |

## Cathedral and church staff

#### C1. Credentials at a glance

As a dean or director of music, I want to see the choir's track record and approach, so that I can judge whether it is a safe pair of hands for a residency.

Given I am evaluating choirs for a residency, when I visit the About and Events pages, then I see what the choir is, how it works, what it sings, and every place it has sung, with dates.

#### C2. A way to make contact

As a dean, I want an obvious way to get in touch about booking.

Given I have decided to invite the choir, when I use the Contact page, then I can send a booking enquiry, which reaches the committee's inbox and their email.

## The public

#### P1. What's on next

As a concert-goer, I want to know where and when the next performance is.

Given I am on the Events page, when a performance is scheduled and marked public, then I see its title, venue, date and time (or "time TBC"), with a booking link or a way to enquire.

#### P2. What they sing

As a prospective singer, I want to see recent performances and repertoire before I apply.

Given I am considering joining, when I read the Events and About pages, then I can see recent programmes and the kind of music the choir sings.

#### P3. Apply to audition

As a prospective singer, I want to apply without hunting for an email address.

Given I am on the Contact page, when I fill in the audition form with my voice part and experience, then the committee receives it and I see a confirmation.

#### P4. Works on my phone

As anyone, I want the site to work properly on a phone.

Given I am on a phone, when I open any public page, then nothing scrolls sideways, buttons are easy to tap, and the menu opens and closes cleanly.

#### P5. Accessible

As someone using a screen reader or a keyboard, I want every page to be usable.

Given I use assistive technology, when I visit any page, then headings, labels, contrast and focus all work, and Lighthouse scores accessibility at 100 on every public page.

## Singers

#### S1. My schedule

As a singer, I want to see upcoming rehearsals and performances for the current project and say whether I am coming.

Given I am logged in, when I open the dashboard, then I see the coming dates, can set Attending or Absent for each, and see any rehearsal plan the committee has written.

#### S2. My music

As a singer, I want my voice part's scores and practice tracks in one place on my phone.

Given I am logged in, when I open my part's hub for the current project, then I can open each score and play or download each track.

#### S3. Practise properly

As a singer learning a hard passage, I want to loop it, slow it down without changing the pitch, and check my starting note.

Given a practice track on my hub, when I open it in the practice player, then I can set a loop start and end, play at 50 to 110 per cent speed, and play any note on an on-screen keyboard. The player remembers where I was.

#### S4. Help plan future projects

As a singer, I want to say whether I am free for a proposed date, with a note if it is complicated.

Given an open availability poll, when I answer it on Looking Ahead, then my answer and note reach the committee.

#### S5. Subscriptions

As a singer, I want to know whether I owe a subscription and how to pay.

Given I have not paid for the current term, when I open the dashboard, then I see the amount, deadline and bank details. Once the committee logs my payment, the card disappears.

#### S6. My details

As a singer, I want to keep my contact details, emergency contact and consents up to date myself.

Given I am logged in, when I use Settings, then I can change them, and my email address is changed through a verified process.

#### S7. Calendar

As a singer, I want rehearsal dates in my own calendar.

Given a scheduled event, when I use "Add to Calendar" for one event or "Add all dates" for a whole project, then I get a calendar file that my calendar app accepts.

## The committee

The committee stories share one acceptance criterion: a committee member can do each of them from the site, on a phone or a computer, without Django admin and without asking a developer.

#### K1. Run the calendar

As a committee member, I want to schedule, edit and delete rehearsals and performances, and write rehearsal plans.

#### K2. See who's coming

As a committee member, I want each event's RSVPs, a one-click reminder to those who have not answered, and everyone's attendance record.

#### K3. Track subscriptions

As the treasurer, I want a ledger of who has paid this term, to log and correct payments, mark people exempt, and look back at earlier terms.

#### K4. Members and invitations

As a committee member, I want to invite new singers by email, edit members' details and roles, and deactivate leavers while keeping their history.

#### K5. Music library

As a committee member, I want to add pieces and upload scores and tracks for each voice part, several files at a time.

#### K6. Email the choir safely

As a committee member, I want to write a broadcast, preview it, send myself a test, and then send it once, with a record of who it reached. Nobody should see anyone else's email address.

#### K7. The contact inbox

As a committee member, I want enquiries and audition applications in one list, to mark them handled, and to clear spam in bulk.

#### K8. Settings without a developer

As a committee member, I want to change the term, subscription amount, bank details and social links myself.

#### K9. Plan with polls

As a committee member, I want to poll availability for a planning-stage project, see the answers and notes, and close the poll when it is decided.

#### K10. Public events

As a committee member, I want the public Events page to update itself when I mark a performance as public.

#### K11. Duty of care

As a committee member, I want a confidential roster of emergency contacts, medical notes and under-18 flags.

#### K12. Committee documents

As a committee member, I want to share minutes and policies with the whole choir, with only the committee able to upload or delete them.

## Maintainer

#### M1. Safe changes

As the maintainer, I want a test suite, a one-command check and seed data, so that I can change the site without breaking it for the choir.

#### M2. No secrets in the repository

As the maintainer, I want credentials kept only in environment variables, and production security settings switched on automatically.

## MoSCoW and status

| Story | Priority | Status |
| --- | --- | --- |
| C1 Credentials at a glance | Must | Done: About page, and the Events page with a database-built archive back to 2012 |
| C2 A way to make contact | Must | Done: booking enquiries reach the committee inbox and email |
| P1 What's on next | Must | Done: next public performance, built from the schedule |
| P2 What they sing | Should | Done: recent performances list their repertoire |
| P3 Apply to audition | Must | Done: audition form, protected by a honeypot |
| P4 Works on my phone | Must | Done: mobile-first pass, checked at 375, 768 and 1366 pixels |
| P5 Accessible | Must | Done: Lighthouse accessibility 100 on all public pages |
| S1 My schedule | Must | Done: dashboard with RSVPs and rehearsal plans; past events folded away |
| S2 My music | Must | Done: voice-part hubs per project |
| S3 Practise properly | Should | Done for loop, speed and note finder. Conductor-marked sections and "My note" are planned ([roadmap](ROADMAP.md)) |
| S4 Help plan future projects | Should | Done: Looking Ahead with notes |
| S5 Subscriptions | Should | Done: amount, deadline and bank details from the committee's settings |
| S6 My details | Must | Done |
| S7 Calendar | Could | Done: per-event and per-project calendar files |
| K1 Run the calendar | Must | Done |
| K2 See who's coming | Must | Done |
| K3 Track subscriptions | Must | Done, with a term selector |
| K4 Members and invitations | Must | Done |
| K5 Music library | Must | Done |
| K6 Email the choir safely | Must | Done: draft, preview, test, send once, per-recipient record |
| K7 The contact inbox | Should | Done, with bulk mark-handled and delete-as-spam |
| K8 Settings without a developer | Should | Done |
| K9 Plan with polls | Should | Done |
| K10 Public events | Should | Done |
| K11 Duty of care | Must | Done |
| K12 Committee documents | Should | Done |
| M1 Safe changes | Must | Done: 196 automated tests, `scripts/dev.py` and seed data |
| M2 No secrets in the repository | Must | Done |

## Won't have, for now

| Item | Reason |
| --- | --- |
| Online card payments | Stripe's fees would take around 1.5% of the choir's subscription income for a task the treasurer does in minutes by bank transfer. The ledger is ready if that changes: payments already record a method and a transaction ID. |
| Public sign-up | Accounts are invite-only. The choir is a closed ensemble, and an open sign-up form would mainly attract spam. |
| A mobile app | The site works well on phones, and an app would double the maintenance for no real gain. |
