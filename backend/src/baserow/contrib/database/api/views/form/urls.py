from django.urls import re_path

from .views import EditRowFormViewView, FormUploadFileView, SubmitFormViewView

app_name = "baserow.contrib.database.api.views.form"

urlpatterns = [
    re_path(
        r"(?P<slug>[-\w]+)/submit/$",
        SubmitFormViewView.as_view(),
        name="submit",
    ),
    re_path(
        r"^(?P<slug>[-\w]+)/upload-file/$",
        FormUploadFileView.as_view(),
        name="upload_file",
    ),
    re_path(
        r"(?P<slug>[-\w]+)/edit-row/(?P<row_token>[^/]+)/$",
        EditRowFormViewView.as_view(),
        name="edit_row",
    ),
]
