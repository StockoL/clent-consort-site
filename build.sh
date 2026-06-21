#!/usr/bin/env bash
# exit on error
set -o errexit

# 1. Install dependencies
pip install -r requirements.txt

# 2. Compile and compress static layout primitives
python manage.py collectstatic --no-input

# 3. Translate models to database schema
python manage.py migrate