# Deployment and development

[Back to README](../README.md)

How to run the site locally, the commands I use for every change, and how the live site is deployed, configured and backed up.

## Contents

- [Running it locally](#running-it-locally)
- [Development commands](#development-commands)
- [Sample data](#sample-data)
- [Changing the design tokens](#changing-the-design-tokens)
- [How I ship a change](#how-i-ship-a-change)
- [Hosting on Render](#hosting-on-render)
- [Environment variables](#environment-variables)
- [Amazon S3](#amazon-s3)
- [Email through Brevo](#email-through-brevo)
- [Backups](#backups)
- [One-off commands on the live database](#one-off-commands-on-the-live-database)

## Running it locally

You need Python 3.12 or later and Git. Node is only needed to change the design tokens.

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

With `DEBUG=True` and no AWS keys, the site uses SQLite, stores uploads on disk and prints emails to the terminal, so nothing local can reach a real service. Then:

```bash
python manage.py migrate
python scripts/dev.py seed
python scripts/dev.py run
```

The site is at http://127.0.0.1:8000/.

## Development commands

`scripts/dev.py` holds the commands I use for every change. It is a Python script rather than a Makefile because `make` is not available on Windows by default.

| Command | Does |
| --- | --- |
| `python scripts/dev.py test` | Collects static files, then runs the test suite |
| `python scripts/dev.py check` | Fails if a model change has no migration, then runs Django's deploy checks against the production settings, with a throwaway key and database URL |
| `python scripts/dev.py run` | Starts the development server |
| `python scripts/dev.py seed` | Fills the local database with sample data |

`check` prints two warnings, W005 and W021, about HSTS subdomains and preload. They are expected while HSTS is kept to one hour.

## Sample data

`seed` creates a committee member, three singers in different voice parts, an active project with past and future events and two pieces with practice files, and a planning project with an open poll. Every account uses the password `choir-dev-password`.

| Email | Role |
| --- | --- |
| `committee@example.com` | Committee |
| `soprano@example.com` | Singer, soprano |
| `alto@example.com` | Singer, alto |
| `tenor@example.com` | Singer, tenor |

The command refuses to run unless `DEBUG=True`. It must never be run against the live database.

## Changing the design tokens

Colours, type sizes and spacing come from `design-tokens.json`. After editing it:

```bash
node build-tokens.js
python manage.py collectstatic --noinput
```

Commit both `design-tokens.json` and the regenerated `choir/static/css/site/global/variables.css`.

## How I ship a change

Render deploys `main` automatically on every push, so a merge to `main` is a release.

1. Work on a branch named for the change.
2. Run `python scripts/dev.py test` and `python scripts/dev.py check`. Both must pass.
3. Check the affected pages in a browser at phone and desktop widths.
4. If the change includes a migration, decide whether a backup is needed first (see [Backups](#backups)).
5. Merge to `main` and push. Render builds and deploys.
6. Run the deploy routine in [Testing](TESTING.md#the-deploy-routine) on the live site.

Migrations are additive only: new fields have a default or allow null, data migrations are kept separate from schema changes, and nothing is removed in the same release as the code that stops using it. That way a deploy that fails part-way leaves the site working.

## Hosting on Render

The site runs as a Render web service on the free plan, with a Render PostgreSQL database on a paid plan. Render runs `build.sh` on every deploy:

```bash
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
```

The free plan has two consequences. The service sleeps when idle, so the first visit after a quiet spell is slow. And there is no Shell tab, so one-off commands are run from my own computer (see [below](#one-off-commands-on-the-live-database)).

## Environment variables

These are set in the Render dashboard and never committed.

| Variable | Used for |
| --- | --- |
| `SECRET_KEY` | Django's signing key |
| `DEBUG` | `False` in production. Anything other than `True` counts as false. |
| `DATABASE_URL` | The PostgreSQL connection string (Render's Internal Database URL) |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | The S3 user's keys. Without them the site stores uploads on disk. |
| `AWS_STORAGE_BUCKET_NAME` | The S3 bucket |
| `BREVO_API_KEY` | Sending email through Brevo |

## Amazon S3

Uploaded scores, tracks and documents live in a private S3 bucket in eu-north-1 (Stockholm). The site hands out presigned links that last six hours.

The practice player needs to read audio files from the bucket to draw a waveform, so the bucket has a CORS rule allowing `GET` and `HEAD` from `https://clentconsort.org` and `https://www.clentconsort.org` only. Without the rule the player still works, with a plain progress bar instead of the waveform.

Existing file paths (`learning_assets/`, `committee_docs/`) must not change, or members' saved links to scores would break.

## Email through Brevo

Render blocks outbound SMTP, so the site sends email through Brevo's HTTP API with django-anymail. Mail comes from `hello@clentconsort.org`, and contact form submissions are sent to the same address.

## Backups

The database is on a paid Render plan, which allows exports. Before deploying a migration I take one:

1. In the Render dashboard, open the database, then Recovery.
2. Choose Create export and wait for it to finish.
3. Download the archive (a `.dir.tar.gz` file) and keep it somewhere safe. Render keeps its own copy for 7 days.

Whether a migration needs a fresh export is a judgement about what would be lost by restoring the last one. During the October 2026 rebuild nobody but me was using the site, so a single export from 26 October covered every deploy.

On a free database plan there are no exports. There, the backup would be a `pg_dump` run from my own computer with the External Database URL.

## One-off commands on the live database

Management commands such as `import_event_archive` sometimes need to run against the live database. With no Shell tab on the free plan, I run them from my own computer:

1. Open a new PowerShell window that will be closed afterwards, so the settings do not linger.
2. Set `DEBUG=False` and `DATABASE_URL` to the database's External Database URL from the Render dashboard.
3. Run the command with `--dry-run` first if it has one, check the output, then run it for real.
4. Close the window.

The External Database URL contains the database password. It should only ever be pasted into that window, never into a file, a chat or a commit.
