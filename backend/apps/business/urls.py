from django.urls import path

from apps.business import views

urlpatterns = [
    path("company/lookup", views.CompanyLookupView.as_view(), name="company-lookup"),
    path("company", views.CompanyView.as_view(), name="company"),
    path("company/members", views.MemberListView.as_view(), name="company-members"),
    path(
        "company/members/<int:member_id>",
        views.MemberDetailView.as_view(),
        name="company-member",
    ),
]
