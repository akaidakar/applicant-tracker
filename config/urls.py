from django.contrib import admin
from django.urls import include, path, re_path

from . import spa

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apply.api_urls")),
    path("", include("apply.urls")),
    # Everything else is a React route. Static files never reach here because
    # WhiteNoise answers them first.
    re_path(r"^(?!api/|admin/|static/|submission$).*$", spa.index),
]
