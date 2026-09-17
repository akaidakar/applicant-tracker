import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone as dj_timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Application, Stage, StageEntry, allowed_next_stages
from .serializers import (
    ApplicantSubmissionSerializer,
    ApplicationDetailSerializer,
    ApplicationListSerializer,
    NoteCreateSerializer,
    NoteSerializer,
    StageChangeSerializer,
    StageEntrySerializer,
    stage_json,
)


def canonical_json(payload):
    """The bytes the client signs: compact separators, sorted keys, UTF-8."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def signature_error(error, message):
    return Response(
        {"success": False, "error": error, "message": message},
        status=status.HTTP_401_UNAUTHORIZED,
    )


def verify_signature(request, payload):
    """Check `X-Signature-256: sha256=<hex>` against HMAC-SHA256 of the canonical payload.

    Returns None when the signature is valid, otherwise a 401 response. The
    error codes match the original gist so the submitter's error handling
    keeps working.
    """
    header = request.headers.get("X-Signature-256")
    if not header:
        return signature_error("missing_signature", "X-Signature-256 header is required")
    if not header.startswith("sha256="):
        return signature_error(
            "invalid_signature_format",
            "X-Signature-256 header must be in format: sha256={hex-digest}",
        )
    provided = header[len("sha256="):]
    try:
        int(provided, 16)
    except ValueError:
        return signature_error(
            "invalid_signature_format", "Signature must be a valid hexadecimal string"
        )
    expected = hmac.new(
        settings.APPLICANT_SIGNING_SECRET.encode("utf-8"), canonical_json(payload), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(provided.lower(), expected):
        return signature_error(
            "signature_mismatch",
            "X-Signature-256 does not match the HMAC-SHA256 of the canonical JSON body "
            "(compact separators, sorted keys, UTF-8).",
        )
    return None


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

        signature_error = verify_signature(request, payload)
        if signature_error:
            return signature_error

        serializer = ApplicantSubmissionSerializer(data=payload)
        if not serializer.is_valid():
            details = [
                f"{field}: {error}"
                for field, errors in serializer.errors.items()
                for error in errors
            ]
            return Response(
                {
                    "success": False,
                    "error": "validation_failed",
                    "message": "One or more fields failed validation",
                    "details": details,
                },
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


# Management API. Session auth and IsAuthenticated come from the DRF defaults
# in settings.


def error_response(error, message, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"success": False, "error": error, "message": message}, status=status_code)


class BadRequest(APIException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, error, message):
        # Set detail directly so the body keeps the same shape as error_response.
        self.detail = {"success": False, "error": error, "message": message}


def parse_bound(params, name):
    raw = params.get(name)
    if not raw:
        return None
    try:
        moment = parse_datetime(raw)
    except ValueError:
        moment = None
    if moment is None:
        raise BadRequest("invalid_filter", f"{name} must be an ISO 8601 datetime.")
    if dj_timezone.is_naive(moment):
        moment = dj_timezone.make_aware(moment, timezone.utc)
    return moment


def with_history(queryset):
    # One query for entries and one for notes, however many stages there are.
    return queryset.prefetch_related("stage_entries__notes")


class ApplicationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ApplicationListView(ListAPIView):
    serializer_class = ApplicationListSerializer
    pagination_class = ApplicationPagination

    def get_queryset(self):
        params = self.request.query_params
        queryset = Application.objects.order_by("-submitted_at", "-id")
        if email := params.get("email"):
            queryset = queryset.filter(email=email)
        if receipt := params.get("receipt"):
            queryset = queryset.filter(receipt=receipt)
        if stage := params.get("stage"):
            if stage not in Stage.values:
                raise BadRequest("invalid_filter", f"stage must be one of: {', '.join(Stage.values)}.")
            queryset = queryset.filter(stage=stage)
        # Both bounds are inclusive.
        if after := parse_bound(params, "submitted_after"):
            queryset = queryset.filter(submitted_at__gte=after)
        if before := parse_bound(params, "submitted_before"):
            queryset = queryset.filter(submitted_at__lte=before)
        return queryset


class ApplicationDetailView(RetrieveAPIView):
    serializer_class = ApplicationDetailSerializer
    queryset = with_history(Application.objects.all())


class ApplicationHistoryView(APIView):
    def get(self, request, pk):
        application = get_object_or_404(with_history(Application.objects.all()), pk=pk)
        return Response({
            "application_id": application.id,
            "current_stage": stage_json(application.stage),
            "history": StageEntrySerializer(application.stage_entries.all(), many=True).data,
        })


class NoteCreateView(APIView):
    def post(self, request, pk):
        serializer = NoteCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("invalid_note", "content is required and cannot be blank.")

        with transaction.atomic():
            # Lock the application so a concurrent stage change can't slip in
            # between reading the current entry and attaching the note.
            application = get_object_or_404(Application.objects.select_for_update(), pk=pk)
            entry = application.current_entry()
            note = entry.notes.create(content=serializer.validated_data["content"])

        return Response(
            {**NoteSerializer(note).data, "stage": stage_json(entry.stage)},
            status=status.HTTP_201_CREATED,
        )


class StageChangeView(APIView):
    def post(self, request, pk):
        serializer = StageChangeSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "invalid_stage", f"stage must be one of: {', '.join(Stage.values)}."
            )
        new_stage = serializer.validated_data["stage"]

        with transaction.atomic():
            # Lock the row so two concurrent moves can't both pass the check
            # against the same old stage.
            application = get_object_or_404(Application.objects.select_for_update(), pk=pk)
            allowed = allowed_next_stages(application.stage)
            if new_stage not in allowed:
                current = Stage(application.stage).label
                if not allowed:
                    message = f"{current} is a final stage. The stage can't change."
                else:
                    options = ", ".join(Stage(s).label for s in allowed)
                    message = (
                        f"Can't move from {current} to {Stage(new_stage).label}. "
                        f"Allowed: {options}."
                    )
                return error_response("invalid_transition", message)

            application.stage = new_stage
            application.save(update_fields=["stage"])
            StageEntry.objects.create(application=application, stage=new_stage)

        fresh = with_history(Application.objects.all()).get(pk=pk)
        return Response(ApplicationDetailSerializer(fresh).data)
