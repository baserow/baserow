from typing import Dict

from baserow.contrib.builder.workflow_actions.workflow_action_types import (
    BuilderWorkflowServiceActionType,
)
from baserow_enterprise.builder.workflow_actions.models import CoreCodeWorkflowAction
from baserow_enterprise.integrations.core.service_types import CoreCodeServiceType


class CoreCodeActionType(BuilderWorkflowServiceActionType):
    type = "code"
    model_class = CoreCodeWorkflowAction
    service_type = CoreCodeServiceType.type

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, int]:
        service = pytest_data_fixture.create_enterprise_core_code_service()
        return {"service": service}
