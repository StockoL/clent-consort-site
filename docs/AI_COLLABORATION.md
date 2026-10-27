# Working with AI

[Back to README](../README.md)

I have used AI tools throughout this project, in different ways at different stages. This page says how, and which decisions stayed with me.

## Contents

- [The static site and Django, April to August 2026](#the-static-site-and-django-april-to-august-2026)
- [The October 2026 rebuild](#the-october-2026-rebuild)
- [What stayed with me](#what-stayed-with-me)
- [What I would tell someone else](#what-i-would-tell-someone-else)

## The static site and Django, April to August 2026

For the first two stages I used Google's Gemini as a pair programmer in conversation. I set the rules of the system myself: the spacing and type scales, the layout patterns and the structure of the Python code. I used Gemini to help track down CSS problems, such as the scrolling fault described in the [development log](DEVELOPMENT_LOG.md#the-100vh-flexbox-trap), and to help move the static pages into Django templates.

I read and edited everything it suggested before using it. It often proposed extra media queries or absolute positioning that would have worked against the layout patterns, and I took those out.

## The October 2026 rebuild

For the rebuild I used Claude Code, an AI coding agent that works directly in the repository: it reads the code, edits files, runs the tests and commands, and drives a browser.

I began by auditing the site and writing a build brief: twelve phases, with ground rules for working on a live site (a branch per phase, additive migrations only, tests for every view, a check of the live site after every deploy). Claude Code then carried out the phases one at a time. For each one it wrote the code and tests, ran the suite and the deploy checks, checked pages in headless Chrome at phone and desktop widths, and reported what it had done and anything it had done differently from the brief, with the reason.

I reviewed each phase before it was merged, tested it myself, and only then let the next one start. Some of the most useful changes came from that testing. I found on my phone that setting a loop while a track played did not hold playback inside it, and asked for the controls to be renamed "Loop start" and "Loop end". I found the committee's navigation too long to swipe through on a phone, chose the drop-down from the options Claude Code described, and checked it before it shipped.

Claude Code also found problems I had not asked about: the honeypot field that had never been on the page, tests uploading files to the live S3 bucket, and a signal that overwrote profile changes. In each case it explained the problem and I decided how to deal with it.

This documentation was drafted with Claude Code from the code, the commit history and my build notes, then reviewed by me. The screenshots in [User journeys](USER_JOURNEYS.md) were captured by a script it wrote, against fictional sample data.

## What stayed with me

- What the site is for, who it serves and what to build next.
- The design: the look, the layout system and the CSS method.
- The ground rules for working on a live site, and the order of the phases.
- Anything that touches production. I take the database backups and decide when one is needed. I make changes to the S3 bucket and Render settings myself. I merge, push and check the live site after every deploy.
- Anything that affects members, such as deleting the spam backlog or which committee members are in the Committee group.

Commits for Phases 0 to 6 of the rebuild credit Claude as co-author. From Phase 7 on they are in my name alone, because I review and own every change. Either way, I am responsible for everything in the repository, whoever or whatever typed it.

## What I would tell someone else

A written brief with explicit rules made the biggest difference. Because the brief said migrations must be additive and every phase must deploy on its own, the agent followed those rules even when a shortcut would have been quicker, and told me when it departed from the brief and why.

Real testing still matters. The automated suite and the scripted browser checks caught many bugs, but the loop problem and the long navigation only showed up when I used the site on my own phone as a singer would.
