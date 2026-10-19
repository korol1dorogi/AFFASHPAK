from django.urls import path

from apps.products import views

urlpatterns = [
    path("products", views.ProductListView.as_view()),
    path("products/<slug:code>", views.ProductDetailView.as_view()),
]
