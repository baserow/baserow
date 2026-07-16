from rest_framework.renderers import JSONRenderer


def _release_serializer_references(serializer):
    """
    Severs the references a DRF serializer graph keeps to the serialized payload. The
    serializer skeleton itself stays cyclic (that is inherent to DRF and small), but
    `instance`, `_args`, `_kwargs`, and `_data` pin the fetched model instances and the
    serialized output, which is where the actual memory sits.
    """

    current = serializer
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        instance_dict = getattr(current, "__dict__", None)
        if not isinstance(instance_dict, dict):
            break
        for attribute in ("instance", "initial_data", "_data", "_validated_data"):
            if attribute in instance_dict:
                instance_dict[attribute] = None
        if "_args" in instance_dict:
            instance_dict["_args"] = ()
        if "_kwargs" in instance_dict:
            instance_dict["_kwargs"] = {}
        current = instance_dict.get("child")


class BaserowJSONRenderer(JSONRenderer):
    """
    DRF creates several reference cycles for every request (see
    https://github.com/encode/django-rest-framework/issues/7250, acknowledged
    upstream but never fixed):

    - `Serializer.data` returns a `ReturnList`/`ReturnDict` with a `serializer`
      backreference, while the serializer keeps the same object in `_data`.
    - `Field.bind` sets `field.parent`, and `BindingDict` keeps a `serializer`
      backreference, so a serializer and its fields always form cycles, pinning
      `serializer.instance` and the `_args`/`_kwargs` stashed by `Field.__new__`
      (which contain the full page of fetched model instances).
    - `APIView.dispatch` sets `view.response`, and `finalize_response` puts the
      view, request, and the response itself into `response.renderer_context`,
      so the response, the rendered content in `response._container`, and the
      request always form cycles.

    Because of those cycles, the per-request object graph (fetched rows, serialized
    data, rendered bytes) can never be freed by reference counting; it lingers until
    Python's cyclic garbage collector runs a full pass, which is allocation-triggered
    and therefore never happens on an idle worker. For large responses that looks like
    a memory leak.

    The `serializer` backreference and the renderer context exist purely so that
    renderers, in practice only the browsable API's `HTMLFormRenderer`, can inspect
    them while rendering. The JSON renderer is the last consumer of both, so after
    producing the bytes it can sever these references. That makes the whole payload
    reference-count collectable the moment the handler drops the response, leaving only
    the small serializer/view skeleton for the regular garbage collector.

    A `JSONRenderer` that, after rendering, breaks the DRF reference cycles described
    in this module's docstring so the per-request payload is freed by reference
    counting instead of lingering as cyclic garbage. The browsable API and any other
    renderer are unaffected because they use their own renderer classes.
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        rendered = super().render(data, accepted_media_type, renderer_context)

        # The serializer output is either the data itself or, for paginated and
        # composite responses, one of the top level values (e.g. under `results`).
        candidates = [data]
        if isinstance(data, dict):
            candidates += list(data.values())
        for candidate in candidates:
            serializer = getattr(candidate, "serializer", None)
            if serializer is not None:
                _release_serializer_references(serializer)

        if isinstance(renderer_context, dict):
            view = renderer_context.get("view")
            if view is not None:
                view.response = None
                view.request = None
                view.args = ()
                view.kwargs = {}
            response = renderer_context.get("response")
            renderer_context.clear()
            if response is not None:
                response.renderer_context = None

        return rendered
