from django.urls import include, path, re_path

from .workflows import urls as workflow_urls

app_name = "baserow.contrib.automation.api"

paths_with_automation_id = [
    path(
        "workflows/",
        include(
            (workflow_urls.urlpatterns_with_automation_id, workflow_urls.app_name),
            namespace="workflows",
        ),
    ),
]

paths_without_automation_id = [
    path(
        "workflows/",
        include(
            (workflow_urls.urlpatterns_without_automation_id, workflow_urls.app_name),
            namespace="workflows",
        ),
    ),
]

urlpatterns = [
    re_path(
        "(?P<automation_id>[0-9]+)/",
        include(
            (paths_with_automation_id, app_name),
            namespace="automation_id",
        ),
    ),
] + paths_without_automation_id
