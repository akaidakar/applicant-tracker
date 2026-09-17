# Applicant tracker

The receiving side of the take-home: a Django app that validates signed
application submissions, issues receipts, and lets recruiters move applicants
through a hiring pipeline. A React frontend sits on top of the API.

Task description: https://gist.github.com/marcua/fadc4c18b84171d9dfab221ba6c36623

## Live app

https://applicant-tracker.fly.dev/

Sign in with the reviewer account (credentials shared separately), then use
the app. Django serves the API and the built frontend from one origin, so the
network tab shows the real `/api/` requests and responses. The database is
seeded with 100 fake applicants on first boot. Notes and stage changes you
make stay there.

## Run it locally

Backend (Python 3.11, Django 5.2, DRF 3.18):

```sh
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser        # the frontend logs in through the admin
python manage.py seed_applications 100  # optional fake data
python manage.py runserver
```

Frontend (Node 22):

```sh
cd frontend
npm install
npm run dev
```

Open http://localhost:5173/admin/login/, sign in with the superuser, then open
http://localhost:5173/. The Vite dev server proxies `/api`, `/admin`, and
`/static` to Django so the browser sees one origin and the session cookie works.

Tests:

```sh
python manage.py test apply     # 34 tests
cd frontend && npm run typecheck && npm run lint
```

Production-style, the way the container runs it:

```sh
cd frontend && npm run build && cd ..
DJANGO_DEBUG=0 python manage.py migrate
DJANGO_DEBUG=0 REVIEWER_PASSWORD=<choose one> python manage.py ensure_reviewer
DJANGO_DEBUG=0 gunicorn config.wsgi:application
```

WhiteNoise serves the built frontend and the admin's static files. Any path
Django doesn't own returns the React app's index.html.

## API

All `/api/` routes require a logged-in session and answer JSON. Every stage in a
response is an object `{"value": "hired", "label": "Hired"}`, so clients never
hardcode labels. Errors from this app look like
`{"success": false, "error": "<code>", "message": "<text>"}`.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/submission` | Receive a signed submission from the applicant's GitHub Action (from the gist, now persists) |
| GET | `/api/applications` | List applications, paginated and filterable |
| GET | `/api/applications/<id>` | One application with every submitted field, current stage, allowed next stages, and history |
| GET | `/api/applications/<id>/history` | The stages the applicant went through, when, and the notes at each |
| POST | `/api/applications/<id>/notes` | Add a note to the applicant's current stage |
| POST | `/api/applications/<id>/stage` | Move the applicant to a later stage |

### List

```
GET /api/applications?email=&receipt=&stage=&submitted_after=&submitted_before=&page=&page_size=
```

`email` and `receipt` match exactly, `stage` is one of the stage values. The
date bounds are inclusive ISO 8601 datetimes. An unknown stage or an
unparseable date returns 400 `invalid_filter`. Results are newest first, 20
per page by default, 100 at most. Each row carries id, name, email,
submitted_at, receipt, and stage.

```json
{
  "count": 100,
  "next": "http://localhost:8000/api/applications?page=2",
  "previous": null,
  "results": [
    {
      "id": 42,
      "name": "Ada Lovelace",
      "email": "ada.lovelace41@example.com",
      "submitted_at": "2026-09-12T02:09:05.982000Z",
      "receipt": "thank-you-from-b12-2026-09-12T02:09:05.982Z-f7e1fdf82378",
      "stage": {"value": "phone_screen_scheduled", "label": "Phone screen scheduled"}
    }
  ]
}
```

### Detail and history

`GET /api/applications/42` returns the list fields plus `resume_link`,
`repository_link`, `action_run_link`, `allowed_next_stages`, and `history`.
`GET /api/applications/42/history` returns the same `history` array with the
application id and current stage:

```json
{
  "application_id": 42,
  "current_stage": {"value": "interview_scheduled", "label": "Interview scheduled"},
  "history": [
    {
      "stage": {"value": "new", "label": "New"},
      "entered_at": "2026-09-12T02:09:05.982000Z",
      "notes": [{"id": 7, "content": "Strong take-home.", "created_at": "2026-09-13T09:12:00Z"}]
    },
    {
      "stage": {"value": "interview_scheduled", "label": "Interview scheduled"},
      "entered_at": "2026-09-15T10:00:00Z",
      "notes": []
    }
  ]
}
```

Entries and notes are oldest first. Skipped stages do not appear.

### Notes

```
POST /api/applications/42/notes   {"content": "Call went well."}
```

Returns 201 with the note and the stage it was attached to. Blank content
returns 400 `invalid_note`. Notes are allowed on final stages.

### Stage change

```
POST /api/applications/42/stage   {"stage": "hired"}
```

Returns the updated application. An unknown stage returns 400
`invalid_stage`. A move that is not forward returns 400 `invalid_transition`
with a message naming the allowed stages, for example
"Can't move from Interview scheduled to Phone screen scheduled. Allowed: Hired, Rejected."

### Submission

`POST /submission` is the gist's endpoint. It parses the body as JSON, checks
`X-Signature-256: sha256=<hex>` against an HMAC-SHA256 of the canonical JSON
(compact separators, sorted keys) with `APPLICANT_SIGNING_SECRET`, validates the
fields, and now saves the application with its first stage entry before
returning the receipt. The error codes are the gist's, so the submitter's
handling keeps working.

## Data model

```
Application         name, email, resume_link, repository_link, action_run_link,
                    submitted_at, receipt (unique), stage
StageEntry          application → Application, stage, entered_at
Note                stage_entry → StageEntry, content, created_at
```

An applicant gets one `StageEntry` per stage they enter. The latest entry is
the current stage. Notes hang off the entry, not off a stage name, so history
groups them with no extra bookkeeping and a note taken at "New" stays under
"New" after a move.

`Application.stage` duplicates the latest entry on purpose. Stage checks and
list filters read one column instead of a subquery, and every write to it
happens in the same transaction as the new entry. The admin shows stage
entries read-only, so the stage endpoint is the only writer and the two can't
drift apart.

`email`, `stage`, and `submitted_at` are indexed because the list filters and
sorts on them. `receipt` is unique, which also indexes it.

## Decisions

**Forward-only stages.** The stage order is the order of the `Stage` choices:
New, Phone screen scheduled, Interview scheduled, Hired, Rejected. A move is
valid when the new stage comes later in that list, as the task requires.
Skipping stages is fine, Rejected is reachable from every other stage
including Hired, and nothing leaves Rejected because nothing follows it.
Sending an applicant backwards returns 400 with the allowed stages named.

**One function holds the rule.** `allowed_next_stages(current)` in
`apply/models.py` validates the stage endpoint and fills `allowed_next_stages`
in the detail response. The frontend builds its dropdown from that field, so it
never re-derives the rule. The server still validates every request.

**Concurrency.** The stage and note endpoints lock the application row with
`select_for_update()` inside `transaction.atomic()`, so two concurrent moves
can't both pass the check against the same old stage. SQLite ignores the lock
but serializes writes; Postgres honors it.

**Duplicate submissions create separate applications.** Email is not unique
and each submission gets its own receipt. Idempotency by hashing the canonical
payload under a unique constraint is the production option, not built here.

**Session auth for the management API, HMAC for submissions.** The
management views use DRF's session authentication with `IsAuthenticated`.
The submission view keeps `authentication_classes = []`, because session
authentication enforces CSRF and the GitHub Action's POST would fail with 403.
Token auth would replace sessions if the frontend moved to another domain.

**Stage is in the list rows.** The task lists five fields for the list
endpoint. `stage` is a sixth because the list page shows it as a column and it
is already a column on the table.

**Frontend stack.** Vite, React 19, TypeScript, `react-router-dom`, plain CSS,
no data library. Two pages didn't justify TanStack Query. Filters and page
number live in the URL, so the back button and shared links work. The stage
picker applies at once; the other filters apply on submit. Date filters send
the start and end of the chosen day in the browser's zone, so "before 17 Sep"
still includes 17 September.

**Deployment.** One Fly.io machine runs gunicorn with the built frontend in
the same image (`Dockerfile`, `fly.toml`). SQLite lives on a volume, so data
survives deploys. On start the container migrates, creates the reviewer user
from the `REVIEWER_PASSWORD` secret, and seeds 100 applicants if the table is
empty. Postgres would replace SQLite before a second machine.

## Layout

```
apply/
  models.py          Application, StageEntry, Note, allowed_next_stages()
  serializers.py     list, detail, history, and input serializers
  views.py           submission view and the /api views
  api_urls.py        /api routes; urls.py keeps the gist's /submission
  admin.py           browse and add notes; stage entries are read-only
  tests.py           33 API and model tests
  management/commands/
    seed_applications.py    fake data; --if-empty for the deploy
    ensure_reviewer.py      the reviewer login, from a secret
config/
  settings.py        env-driven in production, WhiteNoise, SQLite path
  spa.py             serves the built React app for non-API routes
frontend/src/
  api/               http.ts (fetch client), errors.ts, index.ts
  pages/             ApplicationListPage, ApplicationDetailPage
  stages.ts          stage list, mirrors models.py
Dockerfile, fly.toml Fly.io deployment
.github/workflows/ci.yml   Django tests, frontend typecheck, lint, build
```

Deploy:

```sh
fly launch --no-deploy --copy-config --yes   # first time only, creates the app and volume
fly secrets set DJANGO_SECRET_KEY=... APPLICANT_SIGNING_SECRET=... REVIEWER_PASSWORD=...
fly deploy
```
