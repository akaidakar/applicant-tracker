"""Dump every application, with history, as JSON in the shape of GET /api/applications/<id>.

The static demo on GitHub Pages loads this file instead of calling Django, so
the demo shows the exact response shape the real API returns.
"""

import json

from django.core.management.base import BaseCommand

from apply.models import Application
from apply.serializers import ApplicationDetailSerializer


class Command(BaseCommand):
    help = "Print all applications as JSON in the detail endpoint's shape."

    def handle(self, **options):
        queryset = Application.objects.order_by("-submitted_at", "-id").prefetch_related(
            "stage_entries__notes"
        )
        data = ApplicationDetailSerializer(queryset, many=True).data
        self.stdout.write(json.dumps(data, indent=2))
