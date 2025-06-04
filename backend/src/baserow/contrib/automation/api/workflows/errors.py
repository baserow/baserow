from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_AUTOMATION_WORKFLOW_NAME_NOT_UNIQUE = (
    "ERROR_AUTOMATION_WORKFLOW_NAME_NOT_UNIQUE",
    HTTP_400_BAD_REQUEST,
    "The workflow name {e.name} already exists for your automation instance.",
)

ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST = (
    "ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested workflow does not exist.",
)

ERROR_AUTOMATION_WORKFLOW_NOT_IN_AUTOMATION = (
    "ERROR_AUTOMATION_WORKFLOW_NOT_IN_AUTOMATION",
    HTTP_400_BAD_REQUEST,
    "The workflow id {e.workflow_id} does not belong to the automation.",
)

ERROR_AUTOMATION_NODE_DOES_NOT_EXIST = (
    "ERROR_AUTOMATION_NODE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested node does not exist.",
)

ERROR_AUTOMATION_NODE_NOT_IN_WORKFLOW = (
    "ERROR_AUTOMATION_NODE_NOT_IN_WORKFLOW",
    HTTP_400_BAD_REQUEST,
    "The node id {e.node_id} does not belong to the workflow.",
)

ERROR_AUTOMATION_WORKFLOW_IS_EMPTY = (
    "ERROR_AUTOMATION_WORKFLOW_IS_EMPTY",
    HTTP_400_BAD_REQUEST,
    "The workflow {e.workflow_id} contains no nodes, start by adding a trigger.",
)

ERROR_AUTOMATION_NODE_MISCONFIGURED_SERVICE = (
    "ERROR_AUTOMATION_NODE_MISCONFIGURED_SERVICE",
    HTTP_400_BAD_REQUEST,
    "The node {e.node_id} has a misconfigured service.",
)
