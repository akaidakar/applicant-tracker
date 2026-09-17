# Frontend

React 19, TypeScript, Vite, react-router-dom, plain CSS. See the root README
for the API and the design decisions.

```sh
npm install
npm run dev          # http://localhost:5173, proxies /api and /admin to Django on :8000
npm run typecheck
npm run lint
npm run build        # writes dist/, which Django serves in production
```

`src/api/http.ts` is the only place that calls `fetch`. It adds the CSRF
header on POST and turns error bodies into `ApiError`. The pages import from
`src/api`.
