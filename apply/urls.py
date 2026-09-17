from django.urls import re_path

from .views import ApplicantSubmissionView

urlpatterns = [
    re_path(r"^submission$", ApplicantSubmissionView.as_view()),
]
