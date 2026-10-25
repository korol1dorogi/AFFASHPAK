from django.urls import path

from apps.scoring import views

urlpatterns = [
    path("bank/policy", views.BankPolicyView.as_view(), name="bank-policy"),
    path("bank/policy/what-if", views.BankPolicyWhatIfView.as_view(), name="bank-policy-what-if"),
]
