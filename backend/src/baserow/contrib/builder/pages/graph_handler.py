from typing import Dict

from baserow.contrib.builder.elements.exceptions import ElementDoesNotExist
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import Element
from baserow.core.graph.handler import BaseGraphHandler


class PageGraphHandler(BaseGraphHandler):
    """
    The application builder page graph handler is responsible for managing
    the graph of a page.
    """

    base_point_class = Element
    instance_id_mapping = "builder_page_elements"
    does_not_exist_exception = ElementDoesNotExist

    def get_point_map(self) -> Dict[int, Element]:
        return {e.id: e for e in ElementHandler().get_elements(self.instance)}
