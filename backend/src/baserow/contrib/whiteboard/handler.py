from django.db.models import QuerySet

from baserow.contrib.whiteboard.models import Whiteboard

from .exceptions import WhiteboardDoesNotExist


class WhiteboardHandler:
    def get_whiteboard(
        self, whiteboard_id: int, base_queryset: QuerySet | None = None
    ) -> Whiteboard:
        """
        Get a whiteboard by Id.

        :param whiteboard_id: The Id of the whiteboard to retrieve.
        :param base_queryset: Optional queryset to be used.
        :raises WhiteboardDoesNotExist: If the whiteboard doesn't exist.
        :return: The model instance of the requested Whiteboard.
        """

        if base_queryset is None:
            base_queryset = Whiteboard.objects

        try:
            return base_queryset.select_related("workspace").get(id=whiteboard_id)
        except Whiteboard.DoesNotExist:
            raise WhiteboardDoesNotExist
