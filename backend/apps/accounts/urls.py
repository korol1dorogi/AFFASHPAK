from django.urls import path

from apps.accounts import demo_views, views

urlpatterns = [
    path("auth/csrf", views.CsrfView.as_view(), name="auth-csrf"),
    path("auth/register", views.RegisterView.as_view(), name="auth-register"),
    path("auth/login", views.LoginView.as_view(), name="auth-login"),
    path("auth/logout", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/me", views.MeView.as_view(), name="auth-me"),
    path("demo/personas", demo_views.DemoPersonasView.as_view(), name="demo-personas"),
    path("demo/login", demo_views.DemoLoginView.as_view(), name="demo-login"),
]
