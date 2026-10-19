from django.conf import settings
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Бэк-офис: кредитный кабинет (демо)"
admin.site.site_title = "Бэк-офис"

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/", include("apps.core.urls")),
    path("api/", include("apps.documents.urls")),
]

handler404 = "apps.core.exceptions.not_found_view"
handler500 = "apps.core.exceptions.server_error_view"
