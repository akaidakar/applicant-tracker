# B12 applicant management

The receiving side of the take-home: a Django app that validates signed
application submissions, issues receipts, and lets recruiters move applicants
through a hiring pipeline. A React frontend sits on top of the API.

Task description: https://gist.github.com/marcua/fadc4c18b84171d9dfab221ba6c36623

**Live demo:** https://akaidakar.github.io/applicant-tracker/

The demo is the real React app built against an in-browser copy of the API
(`frontend/src/api/demo.ts`) with 100 seeded applicants, because GitHub Pages
cannot run Django. Notes and stage changes persist in your browser until you
press "Reset data". Everything else in this README describes the real stack.

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
python manage.py test apply     # 33 tests
cd frontend && npm run typecheck && npm run lint
```

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
GET /api/applications?email=&receipt=&submitted_after=&submitted_before=&page=&page_size=
```

`email` and `receipt` match exactly. The date bounds are inclusive ISO 8601
datetimes, and an unparseable value returns 400 `invalid_filter`. Results are
newest first, 20 per page by default, 100 at most. Each row carries id, name,
email, submitted_at, receipt, and stage.

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

`email` and `submitted_at` are indexed because the list filters and sorts on
them. `receipt` is unique, which also indexes it.

## Decisions

**Forward-only stages, with two terminal stages.** The stage order is the order
of the `Stage` choices: New, Phone screen scheduled, Interview scheduled,
Hired, Rejected. A move is valid when the new stage comes later in that list,
so skipping stages is fine and Rejected is reachable from any active stage.
Hired and Rejected are final, so nothing moves out of them. This departs from
the literal task text, under which Hired to Rejected would pass the order rule.
Undoing a hire felt like a different operation than a pipeline step, and
dropping that check is a one-line change in `allowed_next_stages()`.

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
number live in the URL, so the back button and shared links work. Date
filters send the start and end of the chosen day in the browser's zone, so
"before 17 Sep" still includes 17 September.

**Demo mode.** `VITE_DEMO=1` swaps the HTTP client for `demo.ts`, which
answers the same four calls from `frontend/src/demo/seed.json`. That file is
the output of `python manage.py export_applications`, which serializes real
rows with the real detail serializer, so the demo shows the exact API shape.
The pages don't know which client they got.

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
    seed_applications.py    fake data for local use
    export_applications.py  dump applications as JSON for the demo
frontend/src/
  api/               http.ts (real), demo.ts (in-browser), index.ts (picks one)
  pages/             ApplicationListPage, ApplicationDetailPage
  stages.ts          stage list and order, mirrors models.py
  demo/seed.json     100 seeded applicants for the demo build
.github/workflows/
  ci.yml             Django tests, frontend typecheck and lint
  pages.yml          builds the demo and deploys it to GitHub Pages
```
