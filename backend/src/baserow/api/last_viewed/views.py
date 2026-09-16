from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import validate_query_parameters
from baserow.api.last_viewed.serializers import (
    LastViewedItemSerializer,
    LastViewedItemsQuerySerializer,
    LastViewedItemsResponseSerializer,
)
from baserow.api.schemas import get_error_schema
from baserow.core.last_viewed.handler import MAX_LISTED_ITEMS, LastViewedHandler


class LastViewedItemsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_ids",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="Comma separated ids of the workspaces to list items "
                "of. Defaults to every workspace the user is a member of.",
            ),
            OpenApiParameter(
                name="types",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="Comma separated item types, optionally limited to a "
                "sub type with `type:sub_type`, like `database_view:grid,builder_page`."
                " Defaults to every type.",
            ),
            OpenApiParameter(
                name="limit",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Maximum number of items to return, 20 by default and "
                "100 at most.",
            ),
            OpenApiParameter(
                name="offset",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description=f"Number of items to skip. The listing pages through at most "
                f"{MAX_LISTED_ITEMS} items, and reports no more items once it "
                f"reaches that depth.",
            ),
        ],
        tags=["Last viewed"],
        operation_id="list_last_viewed_items",
        description=(
            "Lists the views, application pages, dashboards and automation workflows "
            "the authenticated user opened most recently, newest first. Only items "
            "the user can still access are returned."
        ),
        responses={
            200: LastViewedItemsResponseSerializer,
            400: get_error_schema(["ERROR_QUERY_PARAMETER_VALIDATION"]),
        },
    )
    @validate_query_parameters(LastViewedItemsQuerySerializer, return_validated=True)
    def get(self, request, query_params):
        items, has_more = LastViewedHandler.list_items(
            request.user,
            workspace_ids=query_params.get("workspace_ids"),
            type_filters=query_params.get("types"),
            limit=query_params["limit"],
            offset=query_params["offset"],
        )
        return Response(
            {
                "results": LastViewedItemSerializer(
                    items, many=True, context={"request": request}
                ).data,
                "has_more": has_more,
            }
        )
