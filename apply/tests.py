import hashlib
import hmac
import json

from django.test import override_settings
from rest_framework.test import APITestCase

from .models import STAGE_ORDER, TERMINAL, Application, Stage, StageEntry

SECRET = "test-secret"


def sign(payload):
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "sha256=" + hmac.new(SECRET.encode("utf-8"), canonical, hashlib.sha256).hexdigest()


def submission_payload(**overrides):
    payload = {
        "timestamp": "2026-09-16T08:56:58.488Z",
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "resume_link": "https://example.com/resume.pdf",
        "repository_link": "https://github.com/ada/application-submitter",
        "action_run_link": "https://github.com/ada/application-submitter/actions/runs/1",
    }
    payload.update(overrides)
    return payload


class StageModelTests(APITestCase):
    def test_stage_order_matches_pipeline(self):
        self.assertEqual(
            STAGE_ORDER,
            ["new", "phone_screen_scheduled", "interview_scheduled", "hired", "rejected"],
        )

    def test_terminal_stages(self):
        self.assertEqual(TERMINAL, {Stage.HIRED, Stage.REJECTED})


@override_settings(APPLICANT_SIGNING_SECRET=SECRET)
class SubmissionTests(APITestCase):
    def post(self, payload, signature=None):
        body = json.dumps(payload)
        return self.client.post(
            "/submission",
            data=body,
            content_type="application/json",
            headers={"X-Signature-256": signature if signature is not None else sign(payload)},
        )

    def test_signed_submission_creates_application_and_new_entry(self):
        response = self.post(submission_payload())
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["success"])

        application = Application.objects.get()
        self.assertEqual(response.json()["receipt"], application.receipt)
        self.assertTrue(application.receipt.startswith("thank-you-from-b12-"))
        self.assertEqual(application.stage, Stage.NEW)
        self.assertEqual(application.email, "ada@example.com")
        self.assertEqual(application.submitted_at.isoformat(), "2026-09-16T08:56:58.488000+00:00")

        entries = list(StageEntry.objects.filter(application=application))
        self.assertEqual([e.stage for e in entries], [Stage.NEW])

    def test_bad_signature_saves_nothing(self):
        response = self.post(submission_payload(), signature="sha256=" + "0" * 64)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(Application.objects.count(), 0)

    def test_invalid_json(self):
        response = self.client.post(
            "/submission", data="{not json", content_type="application/json",
            headers={"X-Signature-256": "sha256=x"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_json")

    def test_validation_failure_saves_nothing(self):
        response = self.post(submission_payload(resume_link="not a url"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "validation_failed")
        self.assertEqual(Application.objects.count(), 0)

    def test_duplicate_submission_creates_second_application(self):
        self.post(submission_payload())
        response = self.post(submission_payload())
        self.assertEqual(response.status_code, 200)
        receipts = set(Application.objects.values_list("receipt", flat=True))
        self.assertEqual(len(receipts), 2)
