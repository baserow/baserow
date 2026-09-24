from django.urls import path

from .views import SubjectOptionsView

app_name = "baserow.api.subjects"

urlpatterns = [path("", SubjectOptionsView.as_view(), name="list")]
