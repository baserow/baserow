from django.urls import include, path

from .views import urls as views_urls

app_name = "baserow.contrib.database.api.admin"

urlpatterns = [
    path("views/", include(views_urls, namespace="views")),
]
