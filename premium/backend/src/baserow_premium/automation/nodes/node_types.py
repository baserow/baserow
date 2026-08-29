from django.utils.translation import gettext_lazy as _

from baserow.contrib.automation.nodes.node_types import AutomationNodeTriggerType
from baserow_premium.automation.nodes.models import (
    LocalBaserowRowCommentCreatedTriggerNode,
)
from baserow_premium.integrations.local_baserow.service_types import (
    LocalBaserowRowCommentCreatedServiceType,
)


class LocalBaserowRowCommentCreatedNodeTriggerType(AutomationNodeTriggerType):
    type = "local_baserow_row_comment_created"
    model_class = LocalBaserowRowCommentCreatedTriggerNode
    service_type = LocalBaserowRowCommentCreatedServiceType.type
    display_name = _("Local Baserow row comment created")

    def get_pytest_params(self, pytest_data_fixture):
        service = pytest_data_fixture.create_local_baserow_row_comment_created_service()
        return {"service": service}
