from django.urls import re_path

from .views import LastViewedItemsView

app_name = "baserow.api.last_viewed"

urlpatterns = [
    re_path(r"^items/$", LastViewedItemsView.as_view(), name="items"),
]
