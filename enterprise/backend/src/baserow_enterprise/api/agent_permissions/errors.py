from rest_framework.status import HTTP_400_BAD_REQUEST

ERROR_AGENT_RULE_LEAVES_NO_APPROVER = (
    "ERROR_AGENT_RULE_LEAVES_NO_APPROVER",
    HTTP_400_BAD_REQUEST,
    "Nobody could approve tool calls with this rule.",
)
