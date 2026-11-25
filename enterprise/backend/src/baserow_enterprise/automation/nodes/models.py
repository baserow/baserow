from baserow.contrib.automation.nodes.models import (
    AutomationActionNode,
    AutomationTriggerNode,
)


class CoreCodeActionNode(AutomationActionNode): ...


class CoreXLSFileReaderActionNode(AutomationActionNode): ...


class LocalBaserowSemanticSearchActionNode(AutomationActionNode): ...


class LocalBaserowRowCommentPostedTriggerNode(AutomationTriggerNode): ...


class MicrosoftTeamsWriteMessageActionNode(AutomationActionNode): ...
