# User journeys

[Back to README](../README.md)

This page walks through the main routes through the site, one step at a time, with a screenshot of each step. Together they show that each [user story](USER_STORIES.md) works from start to finish.

I took the screenshots on 27 October 2026 from a local copy of the current code, driving headless Chrome over its DevTools protocol so that every form was really filled in and submitted. The copy runs on a fresh database of fictional members, events and enquiries, so no real member's details appear here. The photographs and videos on the public pages are the choir's own. Phone screenshots are at 375 pixels wide and desktop ones at 1366.

## Contents

- [Public visitor](#public-visitor)
  - [Finding out about the choir](#finding-out-about-the-choir)
  - [Sending a booking enquiry](#sending-a-booking-enquiry)
  - [A page that does not exist](#a-page-that-does-not-exist)
- [Singer](#singer)
  - [Logging in](#logging-in)
  - [Checking the schedule and replying](#checking-the-schedule-and-replying)
  - [Learning the music](#learning-the-music)
  - [Answering an availability poll](#answering-an-availability-poll)
  - [Updating my details](#updating-my-details)
- [Committee](#committee)
  - [Finding the tools](#finding-the-tools)
  - [Inviting a new singer](#inviting-a-new-singer)
  - [Scheduling and publishing a performance](#scheduling-and-publishing-a-performance)
  - [Checking who is coming](#checking-who-is-coming)
  - [Logging a subscription payment](#logging-a-subscription-payment)
  - [Adding music](#adding-music)
  - [Polling availability](#polling-availability)
  - [Emailing the choir](#emailing-the-choir)
  - [Working through the inbox](#working-through-the-inbox)
  - [Duty of care, documents and settings](#duty-of-care-documents-and-settings)

## Public visitor

Stories covered: C1, C2, P1 to P5.

### Finding out about the choir

The home page opens on the choir's photograph, with the next project one click away. On a phone the photograph fills the first screen, and an introduction with the next public performance sits below it. The menu opens as a solid panel with the page dimmed behind it.

| Home on a phone | Menu open |
| --- | --- |
| ![Home page on a phone](images/journeys/public/home-phone.jpg) | ![Phone menu open](images/journeys/public/menu-open-phone.jpg) |

![Home page on a desktop](images/journeys/public/home-desktop.jpg)

The About page explains how the choir works and how a project runs. On a phone the background videos are not downloaded; each slide has a Play button instead.

| About on a phone | About on a desktop |
| --- | --- |
| ![About page on a phone](images/journeys/public/about-phone.jpg) | ![About page on a desktop](images/journeys/public/about-desktop.jpg) |

The Events page shows the next public performance, recent performances with their repertoire, and the archive by year. The whole page is built from the committee's schedule.

| Events on a phone | Events on a desktop |
| --- | --- |
| ![Events page on a phone](images/journeys/public/events-phone.jpg) | ![Events page on a desktop](images/journeys/public/events-desktop.jpg) |

### Sending a booking enquiry

A precentor fills in the enquiry form and sends it. The page confirms it was received. The same enquiry appears in the committee's inbox further down this page.

| Form filled in | Sent |
| --- | --- |
| ![Enquiry form filled in](images/journeys/public/contact-enquiry-filled-phone.jpg) | ![Enquiry confirmation](images/journeys/public/contact-enquiry-sent-phone.jpg) |

The audition form sits beside it on the same page.

![Contact page on a desktop](images/journeys/public/contact-desktop.jpg)

### A page that does not exist

A mistyped address gets a branded page with a way back home.

![The 404 page](images/journeys/public/not-found-desktop.jpg)

## Singer

Stories covered: S1 to S7. The singer here is the fictional Sam Soprano.

### Logging in

A wrong password gets a clear message. The right one leads to the dashboard, where a banner confirms the login.

| Wrong password | Correct details |
| --- | --- |
| ![Login error](images/journeys/singer/login-error-phone.jpg) | ![Login form](images/journeys/singer/login-phone.jpg) |

### Checking the schedule and replying

The dashboard starts with the subscription card, because Sam has not paid for this term. It shows the amount, the deadline and the bank details. Below it are the coming dates for each project.

| Dashboard on a phone | Dashboard on a desktop |
| --- | --- |
| ![Dashboard on a phone](images/journeys/singer/dashboard-phone.jpg) | ![Dashboard on a desktop](images/journeys/singer/dashboard-desktop.jpg) |

Opening a date shows the time, the place and the rehearsal plan. Changing the reply to Attending saves straight away and turns the control green. Past dates are folded into "Earlier this project". Each date and each whole project can be added to a calendar.

| Replying to a rehearsal | Earlier dates |
| --- | --- |
| ![RSVP set to attending](images/journeys/singer/rsvp-attending-phone.jpg) | ![Earlier this project opened](images/journeys/singer/earlier-events-phone.jpg) |

### Learning the music

Repertoire lists the current project's pieces and links to each voice part's hub. The hub has the practice player at the top and every score and track for the part below it.

| Repertoire | Soprano hub |
| --- | --- |
| ![Repertoire page](images/journeys/singer/repertoire-phone.jpg) | ![Soprano hub](images/journeys/singer/hub-phone.jpg) |

Here Sam has clicked the waveform at two points and pressed Loop start and Loop end, turned the loop on and slowed the speed to 80%. The shaded band is the loop, and playback stays inside it. The bar along the bottom of the screen keeps the controls in reach while scrolling. The note finder plays any note on the keyboard, for checking a starting note.

| Looping a passage | Note finder |
| --- | --- |
| ![Practice player looping](images/journeys/singer/player-loop-phone.jpg) | ![Note finder keyboard](images/journeys/singer/player-note-finder-phone.jpg) |

![Hub on a desktop](images/journeys/singer/hub-desktop.jpg)

### Answering an availability poll

Looking Ahead lists open polls. Sam answers Maybe and adds a note for the committee. Both save without a submit button, and the page says "Saved."

![Poll answered with a note](images/journeys/singer/looking-ahead-answered-phone.jpg)

### Updating my details

Settings holds name, phone number, voice part, the emergency contact, consent to recordings and photographs, and medical or accessibility notes for the committee. The email address is changed through allauth's verified process. Here Sam changes their phone number, and saving shows a confirmation banner.

![Settings saved](images/journeys/singer/settings-saved-phone.jpg)

## Committee

Stories covered: K1 to K12. The committee member here is the fictional Clara Committee.

### Finding the tools

The Committee Hub links to every tool. On a desktop they are also in the sidebar. On a phone, the Committee button opens them as a grid, labelled with the current page and carrying the inbox count.

| Committee Hub | Committee menu on a phone |
| --- | --- |
| ![Committee Hub](images/journeys/committee/hub-desktop.jpg) | ![Committee drop-down on a phone](images/journeys/committee/nav-dropdown-phone.jpg) |

### Inviting a new singer

Clara enters Oliver Reed's email address, name and voice part, and sends the invitation. He appears under Pending Invitations, where it can be resent. When he signs up, his name and voice part are already filled in. The members list below shows everyone, with their roles and an Under 18 flag.

![Invitation sent](images/journeys/committee/members-invited-desktop.jpg)

Editing a member covers their name, voice part and roles, and deactivating them when they leave.

![Editing a member](images/journeys/committee/member-edit-desktop.jpg)

### Scheduling and publishing a performance

The committee's Events page lists coming events by project, with the form for a new one below. Editing a performance shows the Public Listing section. Ticking "Show on the public Events page" and giving it a title and description is all it takes to put it on the public site.

| Events | Editing a performance |
| --- | --- |
| ![Committee events list](images/journeys/committee/schedule-desktop.jpg) | ![Event edit with public listing](images/journeys/committee/event-edit-public-listing-desktop.jpg) |

### Checking who is coming

Event Logistics shows each event's replies by status. The committee can override a reply, and email everyone who has not answered in one click. Member Overview shows each singer's attendance rate, lowest first. Singers who have not answered anything yet show "No replies yet" rather than a misleading 0%.

| Event logistics | Member overview |
| --- | --- |
| ![RSVPs by event](images/journeys/committee/rsvps-desktop.jpg) | ![Attendance overview](images/journeys/committee/rsvps-overview-desktop.jpg) |

On a phone the overview's table becomes a card per singer.

![RSVPs on a phone](images/journeys/committee/rsvps-phone.jpg)

### Logging a subscription payment

The ledger shows who has paid this term. Clara logs a payment for Alex Alto with the default amount and method; the row turns to Paid and offers Edit and Delete.

| Before | After logging |
| --- | --- |
| ![Ledger](images/journeys/committee/ledger-desktop.jpg) | ![Payment logged](images/journeys/committee/ledger-payment-logged-desktop.jpg) |

![Ledger on a phone](images/journeys/committee/ledger-phone.jpg)

### Adding music

The Music Library lists every piece with its tracks per voice part. On a piece's page Clara uploads an alto practice track. It appears in the list straight away, and on the alto hub.

| Music Library | Track uploaded |
| --- | --- |
| ![Music Library](images/journeys/committee/music-library-desktop.jpg) | ![Track uploaded](images/journeys/committee/piece-uploaded-desktop.jpg) |

### Polling availability

The polling page creates polls and shows results, including each member's note. Sam's "Maybe" from earlier is counted here.

![Polling results](images/journeys/committee/polling-desktop.jpg)

### Emailing the choir

Broadcasts lists drafts and sent emails with delivery counts. A new broadcast is written in a rich text editor and saved as a draft.

| Broadcasts | New broadcast |
| --- | --- |
| ![Broadcasts list](images/journeys/committee/broadcasts-desktop.jpg) | ![New broadcast](images/journeys/committee/broadcast-new-desktop.jpg) |

The preview shows the email as it will arrive and how many people will get it. Clara sends herself a test first. Sending for real needs a ticked confirmation and a confirm dialog, and a broadcast can only be sent once. Afterwards the page records how many were delivered.

| Preview | Test sent |
| --- | --- |
| ![Broadcast preview](images/journeys/committee/broadcast-preview-desktop.jpg) | ![Test sent](images/journeys/committee/broadcast-test-sent-desktop.jpg) |

![Broadcast sent](images/journeys/committee/broadcast-sent-desktop.jpg)

### Working through the inbox

Enquiries and audition applications arrive in one list, unhandled first. The booking enquiry sent from the Contact page earlier is at the top. Each item can be marked handled, and several can be selected at once to mark handled or delete as spam.

![Inbox](images/journeys/committee/inbox-desktop.jpg)

### Duty of care, documents and settings

The Duty of Care roster lists emergency contacts, medical notes and under-18 flags. Documents holds minutes and policies for the whole choir. Choir Settings holds the term, subscription amount, bank details, social links and the switch for the database-built Events page.

| Duty of Care | Documents |
| --- | --- |
| ![Duty of Care roster](images/journeys/committee/duty-of-care-desktop.jpg) | ![Committee documents](images/journeys/committee/documents-desktop.jpg) |

![Choir Settings](images/journeys/committee/choir-settings-desktop.jpg)
