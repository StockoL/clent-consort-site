"""
Development commands, so every phase of work uses the same ones.
Run with the virtualenv's Python from the project root:

    python scripts/dev.py test    # run the test suite
    python scripts/dev.py check   # migration drift + production deploy checks
    python scripts/dev.py run     # local development server
    python scripts/dev.py seed    # local seed data (DEBUG only, never production)

A Python script rather than a Makefile, because make isn't available on
Windows by default.
"""

import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def manage(*args, env=None):
    return subprocess.run(
        [sys.executable, "manage.py", *args], cwd=ROOT, env=env
    ).returncode


def test():
    # Templates resolve {% static %} through the manifest storage, so the
    # manifest must list every static file before the tests render pages.
    status = manage("collectstatic", "--noinput", "--verbosity", "0")
    if status:
        return status
    return manage("test")


def check():
    # 1. No model change without its migration.
    status = manage("makemigrations", "--check", "--dry-run")
    if status:
        return status

    # 2. Deploy checks against production settings. Environment variables
    # win over .env (python-dotenv doesn't override them), so this runs the
    # DEBUG=False branch of settings.py with a throwaway key and database
    # URL - nothing connects to a database. Warnings are printed for review
    # but only errors fail: W005/W021 (HSTS subdomains/preload) are expected
    # while SECURE_HSTS_SECONDS is kept short.
    prod_env = {
        **os.environ,
        "DEBUG": "False",
        "SECRET_KEY": secrets.token_urlsafe(50),
        "DATABASE_URL": "postgres://user:pass@localhost:5432/placeholder",
    }
    return manage("check", "--deploy", env=prod_env)


def run():
    return manage("runserver")


def seed():
    return manage("seed_dev_data")


COMMANDS = {"test": test, "check": check, "run": run, "seed": seed}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit(f"Usage: python scripts/dev.py {{{'|'.join(COMMANDS)}}}")
    sys.exit(COMMANDS[sys.argv[1]]())
