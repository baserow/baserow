# Endpoints

Baserow REST endpoints follow a small, repeatable shape: validate input,
translate domain exceptions, call the service/action/handler, serialize output,
and document the API.

For backend layering see [Architectural patterns](architecture.md).

## File Layout

Most endpoint surfaces live under:

```
backend/src/baserow/<area>/api/<resource>/
├── views.py
├── serializers.py
├── urls.py
└── errors.py
```

Keep request/response serializers, error tuples, views, and routes together.

## View Shape

```python
class WidgetView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[OpenApiParameter("workspace_id", int, OpenApiParameter.PATH)],
        request=WidgetCreateSerializer,
        responses={200: WidgetSerializer, 400: ..., 404: ...},
        tags=["Widgets"],
        operation_id="create_widget",
    )
    @transaction.atomic
    @map_exceptions({
        UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        WidgetDoesNotExist: ERROR_WIDGET_DOES_NOT_EXIST,
    })
    @validate_body(WidgetCreateSerializer)
    def post(self, request, data):
        widget = WidgetService().create_widget(
            request.user, data["workspace_id"], data["name"]
        )
        return Response(WidgetSerializer(widget).data)
```

The view body should be short. If it contains business logic, permission logic,
or custom error-response construction, work is in the wrong layer.

## Validation

Use:

- `@validate_body(Serializer)` for request bodies.
- `@validate_query_parameters(Serializer)` for non-trivial query strings.

Views should not read `request.data` directly. The validated dict passed to the
method is the input contract.

## Error Mapping

Handlers and services raise domain exceptions. Views translate them with
`@map_exceptions`:

```python
@map_exceptions({
    TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
    UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
})
```

`errors.py` defines stable `ERROR_*` tuples:

```python
ERROR_TABLE_DOES_NOT_EXIST = (
    "ERROR_TABLE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested table does not exist.",
)
```

The error code is the API contract the frontend can match on. Do not raise DRF
HTTP exceptions from handlers.

## OpenAPI

Every endpoint should have `@extend_schema`. Set:

- path/query parameters,
- request serializer,
- response serializer or error schemas,
- tags,
- stable `operation_id`.

Changing an `operation_id` is a client-facing API change.

## URL Rules

- Use `urls.py` with named `path(...)` entries.
- Use `<int:...>` for integer ids.
- Use `name="list"` for list endpoints and `name="item"` for single-resource
  endpoints unless the area has an established convention.
- Long-running operations usually get explicit `async_...` names.

## Auth and Permissions

- Authentication is configured on the view (`IsAuthenticated`, `AllowAny`, or
  extra token auth classes).
- Authorization belongs in the service or action via permission checks.
- Public endpoints using `AllowAny` still need explicit public-access checks.
- Database token endpoints must also update the custom token API docs page at
  `web-frontend/modules/database/pages/APIDocsDatabase.vue`.

## Adding an Endpoint

1. Add request/response serializers.
2. Add domain exceptions if the service/handler needs new failure modes.
3. Add `ERROR_*` tuples.
4. Write the view using validation, exception mapping, and `extend_schema`.
5. Add the route.
6. Add API tests for success and mapped error paths.
7. Add or update the matching frontend service.
8. Update custom token API docs if database tokens can call it.

## Anti-Patterns

- Reading `request.data` directly.
- Returning inline `Response({"detail": ...}, status=400)` for domain failures.
- Checking permissions in the view.
- Missing `operation_id`.
- Ad-hoc query parameter parsing.
- Endpoint code that cannot be reused outside HTTP because business logic lives
  in the view.

## Related

- [Creating a feature](creating-features.md).
- [Authentication and sessions](../technical/authentication.md).
- [Project conventions](../development/conventions.md).
