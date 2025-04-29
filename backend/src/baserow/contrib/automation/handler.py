from baserow.contrib.automation.models import Automation
from baserow.core.handler import CoreHandler


class AutomationHandler:
    def get_automation(self, automation_id: int) -> Automation:
        """
        Returns an instance of Automation using its ID.

        :param automation_id: ID of the Automation instance.
        :return: The automation_id instance.
        """

        return (
            CoreHandler()
            .get_application(
                automation_id,
                base_queryset=Automation.objects.select_related("workspace"),
            )
            .specific
        )
