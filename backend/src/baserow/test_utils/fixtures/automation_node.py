from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService


class AutomationNodeFixtures:
    def create_automation_node(self, user=None, **kwargs):
        if user is None:
            user = self.create_user()

        workflow = kwargs.pop("workflow", None)
        if not workflow:
            workflow = self.create_automation_workflow(user=user)

        _node_type = kwargs.pop("node_type", None)
        if _node_type is None:
            node_type = automation_node_type_registry.get("row_created")
        elif isinstance(_node_type, str):
            node_type = automation_node_type_registry.get(_node_type)
        else:
            node_type = _node_type

        if "order" not in kwargs:
            kwargs["order"] = AutomationNode.get_last_order(workflow)

        return AutomationNodeService().create_node(user, node_type, workflow, **kwargs)
