from django.urls import path

from .views import (
    ApplicationDetailView,
    ApplicationHistoryView,
    ApplicationListView,
    NoteCreateView,
    StageChangeView,
)

urlpatterns = [
    path("applications", ApplicationListView.as_view()),
    path("applications/<int:pk>", ApplicationDetailView.as_view()),
    path("applications/<int:pk>/history", ApplicationHistoryView.as_view()),
    path("applications/<int:pk>/notes", NoteCreateView.as_view()),
    path("applications/<int:pk>/stage", StageChangeView.as_view()),
]
