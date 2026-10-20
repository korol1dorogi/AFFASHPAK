from django.urls import path

from apps.recommendations import views

urlpatterns = [
    path("recommendations", views.RecommendationsView.as_view()),
]
