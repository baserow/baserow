from baserow.contrib.automation.models import AutomationWorkflow


class AutomationWorkflowType:
    allowed_fields = ["name"]

    def export_prepared_values(self, workflow: AutomationWorkflow):
        """
        Return a serializable dict of prepared values for the workflow attributes.

        It is called by undo/redo ActionHandler to store the values in a way that
        could be restored later.

        :param instance: The workflow instance to export values for.
        :return: A dict of prepared values.
        """

        return {key: getattr(workflow, key) for key in self.allowed_fields}
