"""Create or update the staff login the reviewer uses on the deployed app.

Run it after a deploy to set or rotate the password from the
REVIEWER_PASSWORD secret. Does nothing when the secret is unset.
"""

import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Ensure the reviewer staff user exists with the password from REVIEWER_PASSWORD."

    def handle(self, **options):
        password = os.environ.get("REVIEWER_PASSWORD")
        if not password:
            self.stdout.write("REVIEWER_PASSWORD is not set; skipping.")
            return
        username = os.environ.get("REVIEWER_USERNAME", "reviewer")
        user, created = User.objects.get_or_create(
            username=username, defaults={"is_staff": True, "is_superuser": True}
        )
        user.set_password(password)
        user.save()
        self.stdout.write(f"{'Created' if created else 'Updated'} user {username}.")
