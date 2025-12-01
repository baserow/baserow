from django.urls import include, path, re_path

from baserow.contrib.automation.api.nodes import urls as node_urls
from baserow.contrib.automation.api.workflows import urls as workflow_urls

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
    path(
        "",
        include(
            node_urls,
            namespace="nodes",
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
