"""
Resolves the workspace tool config of an agent into an effective rule per
tool: `allow` (runs freely), `ask` (pauses for approval) or `off` (hidden).
"""

from .catalog import (
    ROW_TOOL_LOADER,
    ROW_TOOL_OPERATIONS,
    SYNTHETIC_ROW_TOOLS,
    list_workspace_tools,
    to_catalog_name,
)
from .classification import is_write_tool

RULE_ALLOW = "allow"
RULE_ASK = "ask"
RULE_OFF = "off"
RULES = (RULE_ALLOW, RULE_ASK, RULE_OFF)

ACCESS_EVERYTHING = "everything"
ACCESS_READ_ONLY = "read_only"
ACCESS_CUSTOM = "custom"
ACCESS_LEVELS = (ACCESS_EVERYTHING, ACCESS_READ_ONLY, ACCESS_CUSTOM)


def normalize_workspace_config(config: dict | None) -> dict:
    """
    Fills the defaults and translates the pre-rules config keys (`mode`,
    `enabled_tools`) so older rows keep behaving the same.
    """

    config = dict(config or {})
    access = config.get("access")
    if access not in ACCESS_LEVELS:
        access = (
            ACCESS_READ_ONLY if config.get("mode") == "read_only" else ACCESS_EVERYTHING
        )
    require_write_approval = config.get("require_write_approval", True) is not False
    tool_rules = {
        name: rule
        for name, rule in (config.get("tool_rules") or {}).items()
        if rule in RULES
    }

    enabled_tools = config.get("enabled_tools")
    if access != ACCESS_CUSTOM and isinstance(enabled_tools, list):
        enabled = set(enabled_tools)
        access = ACCESS_CUSTOM
        tool_rules = {
            tool["name"]: RULE_OFF
            for tool in list_workspace_tools()
            if tool["name"] not in enabled
            and not (tool["name"] in SYNTHETIC_ROW_TOOLS and ROW_TOOL_LOADER in enabled)
        }

    return {
        "access": access,
        "require_write_approval": require_write_approval,
        "tool_rules": tool_rules,
    }


def default_rule_for(name: str, access: str, require_write_approval: bool) -> str:
    if not is_write_tool(name):
        return RULE_ALLOW
    if access == ACCESS_READ_ONLY:
        return RULE_OFF
    return RULE_ASK if require_write_approval else RULE_ALLOW


def rule_for(config: dict, tool_name: str) -> str:
    """
    The effective rule for a runtime tool name. `config` must be normalized.
    Read tools never ask; the row loader is derived from the row rules.
    """

    name = to_catalog_name(tool_name)
    if name == ROW_TOOL_LOADER:
        return RULE_OFF if not allowed_row_operations(config) else RULE_ALLOW

    access = config["access"]
    rule = None
    if access == ACCESS_CUSTOM:
        rule = config["tool_rules"].get(name)
    if rule is None:
        rule = default_rule_for(name, access, config["require_write_approval"])
    if rule == RULE_ASK and not is_write_tool(name):
        return RULE_ALLOW
    return rule


def allowed_row_operations(config: dict) -> set[str]:
    return {
        operation
        for tool_name, operation in ROW_TOOL_OPERATIONS.items()
        if _row_tool_rule(config, tool_name) != RULE_OFF
    }


def _row_tool_rule(config: dict, name: str) -> str:
    access = config["access"]
    rule = config["tool_rules"].get(name) if access == ACCESS_CUSTOM else None
    return rule or default_rule_for(name, access, config["require_write_approval"])


def materialize_tool_rules(config: dict) -> dict[str, str]:
    """The effective rule of every catalog tool, e.g. to switch to custom."""

    return {
        tool["name"]: rule_for(config, tool["name"]) for tool in list_workspace_tools()
    }


def describe_workspace_access(config: dict) -> str:
    """A summary of the rules for the model's system notes."""

    rules = materialize_tool_rules(config)
    writes = [name for name in rules if is_write_tool(name)]
    enabled_writes = [name for name in writes if rules[name] != RULE_OFF]
    if not enabled_writes:
        return (
            "Baserow workspace tools: read only. You cannot create, update or "
            "delete anything in the workspace."
        )
    note = "Baserow workspace tools: you CAN change the workspace right now."
    row_operations = allowed_row_operations(config)
    if row_operations:
        note += (
            " Row changes ("
            + ", ".join(sorted(row_operations))
            + ") go through load_row_tools first, which gives you the row "
            "tools of a table."
        )
    asking = sorted(name for name in writes if rules[name] == RULE_ASK)
    if len(asking) == len(enabled_writes):
        note += " Every change pauses until a person approves it; that is expected."
    elif asking:
        note += (
            " These changes pause until a person approves them: "
            + ", ".join(asking)
            + "."
        )
    disabled = sorted(name for name in writes if rules[name] == RULE_OFF)
    if disabled:
        note += " These tools are disabled: " + ", ".join(disabled) + "."
    return note
