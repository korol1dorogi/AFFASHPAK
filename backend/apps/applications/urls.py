from django.urls import path

from apps.applications import bank_views, views

urlpatterns = [
    path("applications", views.ApplicationListCreateView.as_view(), name="applications"),
    path("applications/<int:pk>", views.ApplicationDetailView.as_view(), name="application"),
    path("applications/<int:pk>/submit", views.ApplicationSubmitView.as_view()),
    path("applications/<int:pk>/cancel", views.ApplicationCancelView.as_view()),
    path("applications/<int:pk>/hand-off", views.ApplicationHandOffView.as_view()),
    path("applications/<int:pk>/events", views.ApplicationEventsView.as_view()),
    path("applications/<int:pk>/decision", views.ApplicationDecisionView.as_view()),
    path("applications/<int:pk>/offer/accept", views.OfferAcceptView.as_view()),
    path("applications/<int:pk>/offer/decline", views.OfferDeclineView.as_view()),
    path("applications/<int:pk>/signature", views.SignatureStartView.as_view()),
    path("applications/<int:pk>/signature/confirm", views.SignatureConfirmView.as_view()),
    path(
        "applications/<int:pk>/info-requests/<int:request_id>/respond",
        views.InfoRequestRespondView.as_view(),
    ),
    path("bank/applications", bank_views.BankQueueView.as_view(), name="bank-queue"),
    path("bank/dashboard", bank_views.BankDashboardView.as_view(), name="bank-dashboard"),
    path("bank/applications/<int:pk>", bank_views.BankApplicationDetailView.as_view()),
    path("bank/applications/<int:pk>/assign", bank_views.BankAssignView.as_view()),
    path("bank/applications/<int:pk>/approve", bank_views.BankApproveView.as_view()),
    path("bank/applications/<int:pk>/counteroffer", bank_views.BankCounterofferView.as_view()),
    path("bank/applications/<int:pk>/request-info", bank_views.BankRequestInfoView.as_view()),
    path("bank/applications/<int:pk>/decline", bank_views.BankDeclineView.as_view()),
    path("bank/applications/<int:pk>/comments", bank_views.BankCommentView.as_view()),
]
