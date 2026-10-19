from django.urls import path

from apps.documents import views

urlpatterns = [
    path(
        "applications/<int:application_id>/documents",
        views.ApplicationDocumentListView.as_view(),
        name="application-documents",
    ),
    path(
        "applications/<int:application_id>/documents/<int:document_id>",
        views.ApplicationDocumentDownloadView.as_view(),
        name="application-document-download",
    ),
]
