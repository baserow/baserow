# This module previously contained internal_api_request, serializer_to_openapi_inline,
# and NameRoute. These have been removed as part of the MCP server overhaul:
#
# - internal_api_request: replaced by direct service calls in
#   baserow.contrib.database.mcp.services
# - serializer_to_openapi_inline / FullyInlineAutoSchema: removed because MCP tools
#   now use static JSON schemas, not dynamically generated ones from DRF serializers
# - NameRoute: removed because all tools now have static names; match_by_name uses
#   a direct dict lookup
