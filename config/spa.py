"""Serve the built React app for every path Django doesn't own."""

from django.conf import settings
from django.http import FileResponse, HttpResponseNotFound


def index(request, path=""):
    index_html = settings.FRONTEND_DIST / "index.html"
    if not index_html.exists():
        return HttpResponseNotFound(
            "The frontend is not built. Run `npm run build` in frontend/, "
            "or use the Vite dev server on port 5173."
        )
    return FileResponse(open(index_html, "rb"), content_type="text/html")
