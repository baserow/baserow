from typing import Any, Iterator

from rest_framework.renderers import JSONRenderer
from rest_framework.serializers import BaseSerializer


def _iter_serializer_outputs(data: Any) -> Iterator[BaseSerializer]:
    """
    Yields the serializer of every `ReturnList`/`ReturnDict` anywhere in the response
    data tree. Serializer outputs can sit at the top level, inside plain lists (e.g.
    the job and application APIs), or in deeper mappings (e.g. the kanban and calendar
    grouped-row responses).
    """

    stack = [data]
    seen = set()
    while stack:
        node = stack.pop()
        if not isinstance(node, (dict, list, tuple)) or id(node) in seen:
            continue
        seen.add(id(node))
        serializer = getattr(node, "serializer", None)
        if serializer is not None:
            yield serializer
        stack.extend(node.values() if isinstance(node, dict) else node)


def _release_serializer_references(serializer: BaseSerializer) -> None:
    """
    Severs the references a DRF serializer graph keeps to the serialized payload. The
    serializer skeleton itself stays cyclic (that is inherent to DRF and small), but
    `instance`, `_args`, `_kwargs`, `_data`, and `_context` pin the fetched model
    instances, the serialized output, the request, and arbitrary context payloads,
    which is where the actual memory sits.
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
        for attribute in ("_kwargs", "_context"):
            if attribute in instance_dict:
                instance_dict[attribute] = {}
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
    renderers can inspect them while rendering. When this renderer produces the final
    response it is their last consumer, so after producing the bytes it severs these
    references, making the payload reference-count collectable the moment the handler
    drops the response. The cleanup is skipped when another renderer (e.g. the
    browsable API) delegates to this render and still needs the context afterwards.
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        rendered = super().render(data, accepted_media_type, renderer_context)

        response = (
            renderer_context.get("response")
            if isinstance(renderer_context, dict)
            else None
        )
        if response is None or getattr(response, "accepted_renderer", None) is not self:
            return rendered

        for serializer in _iter_serializer_outputs(data):
            _release_serializer_references(serializer)

        view = renderer_context.get("view")
        if view is not None:
            view.response = None
            view.request = None
            view.args = ()
            view.kwargs = {}
        renderer_context.clear()
        response.renderer_context = None

        return rendered
