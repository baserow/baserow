from baserow.core.mcp.groups import GROUP_AUDIT_LOG_READ
from baserow.core.mcp.registries import FunctionMCPTool
from baserow_enterprise.audit_log import tools


class ListAuditLogMcpTool(FunctionMCPTool):
    type = "list_audit_log"
    group = GROUP_AUDIT_LOG_READ
    title = "List the audit log"
    read_only = True
    off_by_default = True
    function = tools.list_audit_log
