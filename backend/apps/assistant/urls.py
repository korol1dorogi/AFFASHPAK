from django.urls import path

from apps.assistant import views

urlpatterns = [
    path("assistant/messages", views.AssistantMessagesView.as_view(), name="assistant-messages"),
    path(
        "assistant/actions/<uuid:action_id>/confirm",
        views.AssistantActionConfirmView.as_view(),
        name="assistant-action-confirm",
    ),
    path(
        "bank/applications/<int:pk>/assistant/messages",
        views.BankAssistantMessagesView.as_view(),
        name="bank-assistant-messages",
    ),
    path(
        "bank/applications/<int:pk>/assistant/summary",
        views.BankAssistantSummaryView.as_view(),
        name="bank-assistant-summary",
    ),
]
