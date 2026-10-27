# Clent Consort

[Live site: clentconsort.org](https://www.clentconsort.org)

I built this site for Clent Consort, a project-based chamber choir from the Clent Hills in Worcestershire that sings services and concerts in cathedrals and historic churches. It does two jobs.

The public pages present the choir to the cathedrals and churches it hopes to sing in, and to audiences and prospective singers: who we are, what we sing, where we perform next and where we have sung before, with ways to book us or apply to audition.

The private members' area replaces email chains and spreadsheets. Singers get their rehearsal schedule and RSVPs, scores and practice tracks for their voice part with a practice player, and availability polls. The committee get the tools to run the choir: members and invitations, the subscriptions ledger, events, broadcasts, the safeguarding roster and the contact inbox.

It is a Django 6 application hosted on Render, with PostgreSQL, files on Amazon S3, email through Brevo, and a hand-written CSS system with no framework.

![The home page on a desktop](docs/images/journeys/public/home-desktop.jpg)

## Documentation

| Document | Contents |
| --- | --- |
| [User stories](docs/USER_STORIES.md) | Who the site is for, what each of them needs, acceptance criteria, and MoSCoW priorities with what is done |
| [User journeys](docs/USER_JOURNEYS.md) | Screenshots of each main route through the site, step by step, as evidence that it works |
| [UX design](docs/UX_DESIGN.md) | Research and the five planes: strategy, scope, structure, skeleton (wireframes) and surface (type, colour, accessibility) |
| [Features](docs/FEATURES.md) | What the public site, the members' area, the practice player and the committee tools do |
| [Architecture](docs/ARCHITECTURE.md) | How it is built: data model, access model, email and file storage, the CSS system and the JavaScript |
| [Testing](docs/TESTING.md) | The automated test suite, browser and accessibility testing, Lighthouse results, validation and bugs found |
| [Deployment and development](docs/DEPLOYMENT.md) | Running it locally, the development commands, deploying to Render, configuration, backups and one-off commands |
| [Committee guide](docs/COMMITTEE_GUIDE.md) | How the committee runs the choir through the site, task by task |
| [Development log](docs/DEVELOPMENT_LOG.md) | How the site was built, phase by phase, with the problems I hit and how I solved them |
| [Roadmap](docs/ROADMAP.md) | What is planned next |
| [Working with AI](docs/AI_COLLABORATION.md) | How I have used AI tools on this project, and which decisions stayed mine |

## Quick start

```bash
git clone https://github.com/StockoL/clent-consort-site.git
cd clent-consort-site
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
SECRET_KEY=any-long-random-string-for-local-use
DEBUG=True
```

Then run:

```bash
python manage.py migrate
python scripts/dev.py seed     # sample members, events and music (local only)
python scripts/dev.py run      # http://127.0.0.1:8000/
python scripts/dev.py test     # the test suite
```

The seeded accounts all use the password `choir-dev-password`. Log in as `committee@example.com` to see the committee tools. [Deployment and development](docs/DEPLOYMENT.md) has the full details.

## Built with

- Python 3 and Django 6.0
- django-allauth and django-invitations for invite-only accounts
- django-anymail with Brevo for email
- django-storages and boto3 with Amazon S3 for scores and recordings
- django-tinymce for rich text
- WhiteNoise for static files
- PostgreSQL in production and SQLite locally
- wavesurfer.js for the practice player's waveform
- Render for hosting

The CSS is my own system, built on LooseLeaf UI and the Every Layout composition patterns, with no CSS or JavaScript framework. [Architecture](docs/ARCHITECTURE.md#css) explains it.

## Credits

- The layout compositions follow Every Layout by Heydon Pickering and Andy Bell.
- Fonts are Cinzel and Inter, from Google Fonts.
- [wavesurfer.js](https://wavesurfer.xyz/) (BSD-3-Clause) is vendored under `choir/static/js/vendor/wavesurfer/`.
- Photographs and recordings belong to the choir.
