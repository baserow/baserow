from django.urls import include, path, re_path

from .data_sources import urls as data_source_urls
from .domains import urls as domain_urls
from .elements import urls as element_urls
from .pages import urls as page_urls
from .preview import urls as preview_urls
from .theme import urls as theme_urls
from .workflow_actions import urls as workflow_action_urls

app_name = "baserow.contrib.builder.api"

paths_with_builder_id = [
    path(
        "pages/",
        include(
            (page_urls.urlpatterns_with_builder_id, page_urls.app_name),
            namespace="pages",
        ),
    ),
    path(
        "domains/",
        include(
            (domain_urls.urlpatterns_with_builder_id, page_urls.app_name),
            namespace="domains",
        ),
    ),
    path(
        "theme/",
        include(
            (theme_urls.urlpatterns_with_builder_id, theme_urls.app_name),
            namespace="theme",
        ),
    ),
]

paths_without_builder_id = [
    path(
        "pages/",
        include(
            (page_urls.urlpatterns_without_builder_id, page_urls.app_name),
            namespace="pages",
        ),
    ),
    path(
        "",
        include(
            element_urls,
            namespace="element",
        ),
    ),
    path(
        "",
        include(
            data_source_urls,
            namespace="data_source",
        ),
    ),
    path(
        "domains/",
        include(
            (domain_urls.urlpatterns_without_builder_id, page_urls.app_name),
            namespace="domains",
        ),
    ),
    path(
        "",
        include(
            (
                workflow_action_urls.urls_without_builder_id,
                workflow_action_urls.app_name,
            ),
            namespace="workflow_action",
        ),
    ),
    path(
        "preview/",
        include(preview_urls, namespace="preview"),
    ),
]

urlpatterns = [
    re_path(
        "(?P<builder_id>[0-9]+)/",
        include(
            (paths_with_builder_id, app_name),
            namespace="builder_id",
        ),
    ),
] + paths_without_builder_id
