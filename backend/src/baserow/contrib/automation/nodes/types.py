from typing import TypeVar

from baserow.contrib.automation.types import AutomationNodeDict
from baserow.contrib.automation.nodes.models import AutomationNode

AutomationNodeDictSubClass = TypeVar("AutomationNodeDictSubClass", bound=AutomationNodeDict)
AutomationNodeSubClass = TypeVar("AutomationNodeSubClass", bound=AutomationNode)
