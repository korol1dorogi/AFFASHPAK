from django.urls import path

from apps.business import views

urlpatterns = [
    path("company/lookup", views.CompanyLookupView.as_view(), name="company-lookup"),
    path("company", views.CompanyView.as_view(), name="company"),
    path("company/metrics", views.CompanyMetricsView.as_view(), name="company-metrics"),
    path(
        "company/integrations/<str:source>/connect",
        views.IntegrationConnectView.as_view(),
        name="company-integration-connect",
    ),
    path("company/members", views.MemberListView.as_view(), name="company-members"),
    path(
        "company/members/<int:member_id>",
        views.MemberDetailView.as_view(),
        name="company-member",
    ),
    path("company/invitations", views.InvitationListView.as_view(), name="company-invitations"),
    path(
        "company/invitations/<int:invitation_id>",
        views.InvitationDetailView.as_view(),
        name="company-invitation",
    ),
    path("invitations", views.MyInvitationListView.as_view(), name="my-invitations"),
    path(
        "invitations/<int:invitation_id>/accept",
        views.InvitationAcceptView.as_view(),
        name="invitation-accept",
    ),
    path(
        "invitations/<int:invitation_id>/decline",
        views.InvitationDeclineView.as_view(),
        name="invitation-decline",
    ),
]
