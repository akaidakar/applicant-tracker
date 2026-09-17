# Applicant tracker

The receiving side of the take-home: a Django app that validates signed
application submissions, issues receipts, and lets recruiters move applicants
through a hiring pipeline. A React frontend sits on top of the API.

## Live app

https://applicant-tracker-six.vercel.app/

Sign in with the reviewer account (credentials shared separately), then use
the app. The API and the frontend share one origin, so the network tab shows
the real `/api/` requests and responses. The database holds 100 seeded
applicants. Notes and stage changes you make stay there. The first request
after a quiet spell takes a second while the function starts.

"Test submission" in the top bar opens a page that does what the applicant's
GitHub Action does: it signs a payload with HMAC-SHA256 in the browser and
POSTs it to `/submission`. One button sends a valid submission and gets a
receipt and a new row in the list. The others send a wrong secret, no
signature, a missing field, and a body that isn't JSON, and each shows the
gist's error code for it. The page needs the deployment's signing secret,
shared with the login. It also prints the same request as a curl and openssl
snippet for use outside the browser.

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
python manage.py test apply     # 42 tests
cd frontend && npm run typecheck && npm run lint
```

Production-style, with the built frontend served by Django:

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
response is an object `{"value": "hired", "label": "Hired"}`, so clients don't
need to hardcode labels for anything they display. Errors this app raises look
like `{"success": false, "error": "<code>", "message": "<text>"}`. The
submission endpoint's `validation_failed` error adds a `details` list naming
each bad field, as in the gist. An unknown id
or a request without a session gets DRF's `{"detail": "<text>"}` with 404 or 403.

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

`receipt` matches exactly, `email` matches ignoring case, and `stage` is one
of the stage values. The date bounds are inclusive ISO 8601 datetimes. A bare
date such as `2026-09-17` means the whole day in UTC, so `submitted_before`
includes it. An unknown stage or an unparseable date returns 400
`invalid_filter`. Results are newest first, 20
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
returns 400 `invalid_note`. Notes are allowed on every stage, including Rejected.

### Stage change

```
POST /api/applications/42/stage   {"stage": "hired"}
```

Returns the updated application. An unknown stage returns 400
`invalid_stage`. A move that is not forward returns 400 `invalid_transition`
with a message naming the allowed stages, for example
"Can't move from Interview scheduled to Phone screen scheduled. Allowed: Hired, Rejected."
A bad or out-of-range `page` on the list returns 400 `invalid_page`.

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
list filters read one column instead of a subquery. `Application.objects.submit()`
creates a row at New together with its first entry, and `Application.enter_stage()`
is the only code that changes the column afterwards, creating the entry in the
same transaction. The submission endpoint, the seed command, and the tests use
`submit()`. The stage endpoint, the admin's add form, and the notes endpoint's
fallback for a row with no entries use `enter_stage()`. The admin shows stage
entries read-only and blocks deleting them, so nothing else can make the two
drift apart.

Indexes match the list's queries. `(-submitted_at, -id)` is the unfiltered
newest-first sort, `(stage, -submitted_at, -id)` is the same sort with the
stage filter, and each is one index scan with no sort step. `email` has an
index on `UPPER(email)`, which is what Postgres compiles the case-insensitive
filter to. `receipt` is unique, which also indexes it.

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

**History orders by id, not date.** Stage entries sort in the order the moves
were made. The date is for display, so seeded or hand-edited dates can't
change which entry counts as current or where a new note attaches.

**Concurrency.** The stage and note endpoints lock the application row with
`select_for_update()` inside `transaction.atomic()`, so two concurrent moves
can't both pass the check against the same old stage. Postgres honors the
lock. SQLite ignores it, so the SQLite connection opens every transaction
in IMMEDIATE mode, which takes the write lock up front and makes the second
request wait instead of failing with "database is locked".

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

**Deployment.** On Vercel (`vercel.json`) the frontend is static and Django
runs as a function. Vercel serves the built files itself, routes `/api`,
`/admin`, `/static`, and `/submission` to Django, and every other path to the
React app. A function has no disk, so `DATABASE_URL` points at Neon Postgres,
and migrations run from a laptop against it.

## Layout

```
apply/
  models.py          Application (enter_stage), StageEntry, Note, allowed_next_stages(), make_receipt()
  serializers.py     list, detail, history, and input serializers
  views.py           submission view and the /api views
  api_urls.py        /api routes; urls.py keeps the gist's /submission
  admin.py           browse and add notes; stage entries are read-only
  tests.py           API and model tests
  management/commands/
    seed_applications.py    fake data; --if-empty for the deploy
    ensure_reviewer.py      the reviewer login, from a secret
config/
  settings.py        env-driven in production, WhiteNoise, SQLite path
  spa.py             serves the built React app for non-API routes
frontend/src/
  api/               http.ts (fetch client), errors.ts, index.ts
  pages/             ApplicationListPage, ApplicationDetailPage, SubmissionTestPage
  signing.ts         canonical JSON and HMAC signing for the submission tester
  stages.ts          stage list for the filter picker, the one copy of models.py's list on the client
vercel.json          Vercel: static frontend plus a Django function
.github/workflows/ci.yml   Django tests, frontend typecheck, lint, build
```

Deploy to Vercel:

```sh
vercel link
vercel integration add neon                  # creates the database and sets DATABASE_URL
for name in DJANGO_DEBUG DJANGO_ALLOWED_HOSTS CSRF_TRUSTED_ORIGINS \
            DJANGO_SECRET_KEY APPLICANT_SIGNING_SECRET REVIEWER_PASSWORD; do
  vercel env add $name production           # 0, .vercel.app, https://<project>.vercel.app, and three secrets
done
vercel env pull --environment production .env.production
export DATABASE_URL="$(grep '^DATABASE_URL=' .env.production | cut -d= -f2- | tr -d '"')"
python manage.py migrate
REVIEWER_PASSWORD=<the one you set> python manage.py ensure_reviewer
python manage.py seed_applications 100 --if-empty
vercel deploy --prod
```

Vercel marks the secrets as sensitive, so `env pull` writes a placeholder for
them, and only `DATABASE_URL` comes through. The management commands run with
Django's local defaults and that one variable. If libpq reports "certificate
verify failed", a stray `~/.postgresql/root.crt` is being used to verify Neon.
Point it at the real bundle instead:

```sh
export DATABASE_URL="${DATABASE_URL/sslmode=require/sslmode=verify-full}&sslrootcert=/etc/ssl/cert.pem"
```
