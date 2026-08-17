#!/bin/sh

set -eu

python manage.py send_billing_reminders
python manage.py cleanup_security_data
python manage.py purge_scheduled_organizations
