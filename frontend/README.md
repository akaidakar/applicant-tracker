# Frontend

React 19, TypeScript, Vite, react-router-dom, plain CSS. See the root README
for the API and the design decisions.

```sh
npm install
npm run dev          # http://localhost:5173, proxies /api and /admin to Django on :8000
npm run typecheck
npm run lint
npm run build        # real app, calls the Django API on the same origin
npm run build:demo   # GitHub Pages build: in-browser API, base path /applicant-tracker/
```

`src/api/index.ts` picks the client. With `VITE_DEMO=1` it exports the
functions from `demo.ts`, which answer from `src/demo/seed.json` and persist
changes in localStorage. Otherwise it exports `http.ts`. The pages import from
`../api` and don't know which one they got.

Regenerate the seed from a seeded Django database with:

```sh
python manage.py export_applications > frontend/src/demo/seed.json
```
