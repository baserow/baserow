from django.urls import re_path

from baserow.api.user_sources.authentication import UserSourceJSONWebTokenAuthentication
from baserow.api.user_sources.views import (
    UserSourceObtainJSONWebToken,
    UserSourceTokenRefreshView,
)
from baserow.contrib.builder.api.domains.public_views import (
    PublicBuilderByIdView,
    PublicBuilderWorkflowActionsView,
    PublicDataSourcesView,
    PublicDispatchDataSourcesView,
    PublicDispatchDataSourceView,
    PublicElementsView,
)
from baserow.contrib.builder.api.preview.views import (
    BuilderPreviewExchangeView,
    BuilderPreviewGrantView,
    BuilderPreviewHandoffView,
)
from baserow.contrib.builder.api.workflow_actions.views import (
    DispatchBuilderWorkflowActionView,
)
from baserow.contrib.builder.preview.authentication import (
    BuilderPreviewAuthentication,
)

app_name = "baserow.contrib.builder.api.preview"

PREVIEW_AUTHENTICATION_CLASSES = (
    BuilderPreviewAuthentication,
    UserSourceJSONWebTokenAuthentication,
)

urlpatterns = [
    re_path(
        r"(?P<builder_id>[0-9]+)/grant/$",
        BuilderPreviewGrantView.as_view(),
        name="grant",
    ),
    re_path(
        r"exchange/(?P<token>[^/]+)/$",
        BuilderPreviewExchangeView.as_view(),
        name="exchange",
    ),
    re_path(
        r"handoff/$",
        BuilderPreviewHandoffView.as_view(),
        name="handoff",
    ),
    re_path(
        r"(?P<builder_id>[0-9]+)/current/$",
        PublicBuilderByIdView.as_view(
            authentication_classes=(BuilderPreviewAuthentication,),
            schema=None,
        ),
        name="current",
    ),
    re_path(
        r"(?P<builder_id>[0-9]+)/pages/(?P<page_id>[0-9]+)/elements/$",
        PublicElementsView.as_view(
            authentication_classes=PREVIEW_AUTHENTICATION_CLASSES,
            schema=None,
        ),
        name="list_elements",
    ),
    re_path(
        r"(?P<builder_id>[0-9]+)/pages/(?P<page_id>[0-9]+)/data-sources/$",
        PublicDataSourcesView.as_view(
            authentication_classes=PREVIEW_AUTHENTICATION_CLASSES,
            schema=None,
        ),
        name="list_data_sources",
    ),
    re_path(
        r"(?P<builder_id>[0-9]+)/pages/(?P<page_id>[0-9]+)/workflow-actions/$",
        PublicBuilderWorkflowActionsView.as_view(
            authentication_classes=PREVIEW_AUTHENTICATION_CLASSES,
            schema=None,
        ),
        name="list_workflow_actions",
    ),
    re_path(
        r"(?P<builder_id>[0-9]+)/data-sources/"
        r"(?P<data_source_id>[0-9]+)/dispatch/$",
        PublicDispatchDataSourceView.as_view(
            authentication_classes=PREVIEW_AUTHENTICATION_CLASSES,
            schema=None,
        ),
        name="dispatch_data_source",
    ),
    re_path(
        r"(?P<builder_id>[0-9]+)/pages/(?P<page_id>[0-9]+)/"
        r"dispatch-data-sources/$",
        PublicDispatchDataSourcesView.as_view(
            authentication_classes=PREVIEW_AUTHENTICATION_CLASSES,
            schema=None,
        ),
        name="dispatch_data_sources",
    ),
    re_path(
        r"(?P<builder_id>[0-9]+)/workflow-actions/"
        r"(?P<workflow_action_id>[0-9]+)/dispatch/$",
        DispatchBuilderWorkflowActionView.as_view(
            authentication_classes=PREVIEW_AUTHENTICATION_CLASSES,
            schema=None,
        ),
        name="dispatch_workflow_action",
    ),
    re_path(
        r"(?P<builder_id>[0-9]+)/user-sources/"
        r"(?P<user_source_id>[0-9]+)/token-auth/$",
        UserSourceObtainJSONWebToken.as_view(
            authentication_classes=(BuilderPreviewAuthentication,),
            schema=None,
        ),
        name="user_source_token_auth",
    ),
    re_path(
        r"(?P<builder_id>[0-9]+)/user-source-auth-refresh/$",
        UserSourceTokenRefreshView.as_view(
            authentication_classes=(BuilderPreviewAuthentication,),
            schema=None,
        ),
        name="user_source_token_refresh",
    ),
]
