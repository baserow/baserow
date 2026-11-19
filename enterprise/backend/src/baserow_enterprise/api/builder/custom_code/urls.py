from django.urls import re_path

from rest_framework.renderers import JSONRenderer

from .serializers import CustomHtmlSerializer
from .views import CustomCodeView, PublicCustomCodeView

app_name = "baserow_enterprise.api.custom_code"

preview_urlpatterns = [
    re_path(
        r"^(?P<builder_id>[0-9]+)/custom-code/html/$",
        CustomCodeView.as_view(
            renderer_classes=(JSONRenderer,),
            serializer_class=CustomHtmlSerializer,
            operation_id="get_preview_builder_custom_html",
        ),
        {"code_type": "html"},
        name="html",
    ),
    re_path(
        r"^(?P<builder_id>[0-9]+)/custom-code/css/$",
        CustomCodeView.as_view(),
        {"code_type": "css"},
        name="css",
    ),
    re_path(
        r"^(?P<builder_id>[0-9]+)/custom-code/js/$",
        CustomCodeView.as_view(),
        {"code_type": "js"},
        name="js",
    ),
]

urlpatterns = [
    re_path(
        r"^(?P<builder_id>[0-9]+)/html/public/$",
        PublicCustomCodeView.as_view(
            renderer_classes=(JSONRenderer,),
            serializer_class=CustomHtmlSerializer,
            operation_id="get_public_builder_custom_html",
        ),
        {"code_type": "html"},
        name="public_html",
    ),
    re_path(
        r"^(?P<builder_id>[0-9]+)/css/public/$",
        PublicCustomCodeView.as_view(),
        {"code_type": "css"},
        name="public_css",
    ),
    re_path(
        r"^(?P<builder_id>[0-9]+)/js/public/$",
        PublicCustomCodeView.as_view(),
        {"code_type": "js"},
        name="public_js",
    ),
]
