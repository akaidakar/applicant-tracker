import hashlib
import hmac
import json
from datetime import datetime, timezone

from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import STAGE_ORDER, TERMINAL, Application, Note, Stage, StageEntry, allowed_next_stages

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

    def test_allowed_next_stages(self):
        self.assertEqual(
            allowed_next_stages("new"),
            ["phone_screen_scheduled", "interview_scheduled", "hired", "rejected"],
        )
        self.assertEqual(allowed_next_stages("interview_scheduled"), ["hired", "rejected"])
        self.assertEqual(allowed_next_stages("hired"), [])
        self.assertEqual(allowed_next_stages("rejected"), [])


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
        self.assertEqual(response.json()["error"], "signature_mismatch")
        self.assertEqual(Application.objects.count(), 0)

    def test_signature_error_codes(self):
        cases = [
            ("", "missing_signature"),
            ("md5=abc", "invalid_signature_format"),
            ("sha256=not-hex", "invalid_signature_format"),
        ]
        for signature, error in cases:
            response = self.post(submission_payload(), signature=signature)
            self.assertEqual(response.status_code, 401, signature)
            self.assertEqual(response.json()["error"], error)

    def test_uppercase_hex_signature_is_accepted(self):
        payload = submission_payload()
        response = self.post(payload, signature=sign(payload).upper().replace("SHA256=", "sha256="))
        self.assertEqual(response.status_code, 200, response.content)

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


def make_application(n=1, submitted_at=None, **fields):
    application = Application.objects.create(
        name=fields.get("name", f"Applicant {n}"),
        email=fields.get("email", f"applicant{n}@example.com"),
        resume_link="https://example.com/resume.pdf",
        repository_link="https://github.com/x/y",
        action_run_link="https://github.com/x/y/actions/runs/1",
        submitted_at=submitted_at or datetime(2026, 9, 1, 12, tzinfo=timezone.utc),
        receipt=fields.get("receipt", f"thank-you-from-b12-test-{n}"),
        stage=Stage.NEW,
    )
    StageEntry.objects.create(application=application, stage=Stage.NEW)
    return application


class ApiTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("recruiter", password="pw", is_staff=True)
        self.client.force_authenticate(self.user)
        self.app = make_application()

    def move(self, stage, app=None):
        return self.client.post(
            f"/api/applications/{(app or self.app).id}/stage", {"stage": stage}, format="json"
        )

    def note(self, content, app=None):
        return self.client.post(
            f"/api/applications/{(app or self.app).id}/notes", {"content": content}, format="json"
        )


class StageChangeTests(ApiTestCase):
    def assert_stages(self, expected):
        self.app.refresh_from_db()
        self.assertEqual(self.app.stage, expected[-1])
        self.assertEqual(list(self.app.stage_entries.values_list("stage", flat=True)), expected)

    def test_forward_move(self):
        response = self.move("phone_screen_scheduled")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["stage"]["value"], "phone_screen_scheduled")
        self.assert_stages(["new", "phone_screen_scheduled"])

    def test_skip(self):
        self.assertEqual(self.move("interview_scheduled").status_code, 200)
        self.assert_stages(["new", "interview_scheduled"])

    def test_rejected_from_new(self):
        self.assertEqual(self.move("rejected").status_code, 200)
        self.assert_stages(["new", "rejected"])

    def test_hired_is_terminal(self):
        self.move("hired")
        response = self.move("rejected")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_transition")
        self.assert_stages(["new", "hired"])

    def test_backwards_rejected(self):
        self.move("interview_scheduled")
        response = self.move("phone_screen_scheduled")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Allowed: Hired, Rejected", response.json()["message"])
        self.assert_stages(["new", "interview_scheduled"])

    def test_same_stage_rejected(self):
        self.assertEqual(self.move("new").status_code, 400)
        self.assert_stages(["new"])

    def test_unknown_stage(self):
        response = self.move("promoted")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_stage")

    def test_missing_application(self):
        response = self.client.post("/api/applications/999/stage", {"stage": "hired"}, format="json")
        self.assertEqual(response.status_code, 404)


class NoteAndHistoryTests(ApiTestCase):
    def test_note_stays_under_its_stage_after_a_move(self):
        response = self.note("Great take-home")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["stage"], {"value": "new", "label": "New"})
        self.move("phone_screen_scheduled")
        self.note("Call went well")

        response = self.client.get(f"/api/applications/{self.app.id}/history")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["application_id"], self.app.id)
        self.assertEqual(body["current_stage"]["value"], "phone_screen_scheduled")
        self.assertEqual(
            [(h["stage"]["value"], [n["content"] for n in h["notes"]]) for h in body["history"]],
            [("new", ["Great take-home"]), ("phone_screen_scheduled", ["Call went well"])],
        )

    def test_note_allowed_on_terminal_stage(self):
        self.move("rejected")
        self.assertEqual(self.note("Not enough depth").status_code, 201)

    def test_blank_note(self):
        response = self.note("   ")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Note.objects.count(), 0)

    def test_note_on_application_without_entries_creates_one(self):
        # A row made by hand in the admin or shell has no StageEntry yet.
        bare = Application.objects.create(
            name="Bare", email="bare@example.com", resume_link="https://x.io/r",
            repository_link="https://x.io/g", action_run_link="https://x.io/a",
            submitted_at=datetime(2026, 9, 1, tzinfo=timezone.utc), receipt="bare-1",
            stage=Stage.INTERVIEW_SCHEDULED,
        )
        response = self.note("first", app=bare)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["stage"]["value"], "interview_scheduled")
        self.assertEqual(list(bare.stage_entries.values_list("stage", flat=True)), ["interview_scheduled"])

    def test_note_missing_application(self):
        response = self.client.post("/api/applications/999/notes", {"content": "x"}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_history_query_count_does_not_grow_with_stages(self):
        self.move("phone_screen_scheduled")
        self.move("interview_scheduled")
        self.note("a")
        # Auth is forced, so only: application, stage entries, notes.
        with self.assertNumQueries(3):
            self.client.get(f"/api/applications/{self.app.id}/history")


class DetailTests(ApiTestCase):
    def test_detail_shape(self):
        self.move("interview_scheduled")
        body = self.client.get(f"/api/applications/{self.app.id}").json()
        self.assertEqual(body["stage"], {"value": "interview_scheduled", "label": "Interview scheduled"})
        self.assertEqual(
            body["allowed_next_stages"],
            [{"value": "hired", "label": "Hired"}, {"value": "rejected", "label": "Rejected"}],
        )
        self.assertEqual(body["resume_link"], "https://example.com/resume.pdf")
        self.assertEqual(len(body["history"]), 2)

    def test_missing(self):
        self.assertEqual(self.client.get("/api/applications/999").status_code, 404)


class ListTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.older = make_application(
            2, submitted_at=datetime(2026, 8, 1, 9, tzinfo=timezone.utc), email="old@example.com"
        )
        self.newer = make_application(3, submitted_at=datetime(2026, 9, 10, 9, tzinfo=timezone.utc))

    def ids(self, response):
        self.assertEqual(response.status_code, 200, response.content)
        return [r["id"] for r in response.json()["results"]]

    def test_newest_first_with_slim_fields(self):
        response = self.client.get("/api/applications")
        self.assertEqual(self.ids(response), [self.newer.id, self.app.id, self.older.id])
        self.assertEqual(
            set(response.json()["results"][0]),
            {"id", "name", "email", "submitted_at", "receipt", "stage"},
        )

    def test_filter_email_and_receipt(self):
        self.assertEqual(self.ids(self.client.get("/api/applications?email=old@example.com")), [self.older.id])
        self.assertEqual(
            self.ids(self.client.get(f"/api/applications?receipt={self.newer.receipt}")), [self.newer.id]
        )

    def test_date_bounds_are_inclusive(self):
        response = self.client.get(
            "/api/applications",
            {"submitted_after": "2026-09-01T12:00:00Z", "submitted_before": "2026-09-10T09:00:00Z"},
        )
        self.assertEqual(self.ids(response), [self.newer.id, self.app.id])

    def test_bad_date(self):
        response = self.client.get("/api/applications?submitted_after=yesterday")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_filter")

    def test_pagination(self):
        body = self.client.get("/api/applications?page_size=2").json()
        self.assertEqual(body["count"], 3)
        self.assertEqual(len(body["results"]), 2)
        self.assertIsNotNone(body["next"])
        page2 = self.client.get("/api/applications?page_size=2&page=2").json()
        self.assertEqual([r["id"] for r in page2["results"]], [self.older.id])


@override_settings(APPLICANT_SIGNING_SECRET=SECRET)
class AuthTests(APITestCase):
    def test_management_api_requires_login(self):
        app = make_application()
        for url in ["/api/applications", f"/api/applications/{app.id}", f"/api/applications/{app.id}/history"]:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        response = self.client.post(f"/api/applications/{app.id}/stage", {"stage": "hired"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_submission_still_works_without_login_and_with_csrf_checks(self):
        from rest_framework.test import APIClient

        client = APIClient(enforce_csrf_checks=True)
        payload = submission_payload()
        response = client.post(
            "/submission", data=json.dumps(payload), content_type="application/json",
            headers={"X-Signature-256": sign(payload)},
        )
        self.assertEqual(response.status_code, 200, response.content)
