import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone

from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Application, Stage, StageEntry
from .serializers import ApplicantSubmissionSerializer


def make_receipt():
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return f"thank-you-from-b12-{now}-{secrets.token_hex(6)}"


class ApplicantSubmissionView(APIView):
    # No session auth here: SessionAuthentication would enforce CSRF and the
    # GitHub Action's POST would fail with 403. The HMAC signature is the auth.
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return Response(
                {"success": False, "error": "invalid_json", "message": "Body must be valid JSON."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        header = request.headers.get("X-Signature-256", "")
        if not header.startswith("sha256="):
            return Response(
                {"success": False, "error": "invalid_signature", "message": "Missing or malformed signature."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        expected = hmac.new(
            settings.APPLICANT_SIGNING_SECRET.encode("utf-8"), canonical, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, header[len("sha256="):]):
            return Response(
                {"success": False, "error": "invalid_signature", "message": "Signature does not match."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = ApplicantSubmissionSerializer(data=payload)
        if not serializer.is_valid():
            details = [f"{field}: {'; '.join(str(e) for e in errors)}" for field, errors in serializer.errors.items()]
            return Response(
                {"success": False, "error": "validation_failed", "details": details},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        with transaction.atomic():
            application = Application.objects.create(
                name=data["name"],
                email=data["email"],
                resume_link=data["resume_link"],
                repository_link=data["repository_link"],
                action_run_link=data["action_run_link"],
                submitted_at=data["timestamp"],
                receipt=make_receipt(),
                stage=Stage.NEW,
            )
            StageEntry.objects.create(application=application, stage=Stage.NEW)

        return Response({"success": True, "receipt": application.receipt})
