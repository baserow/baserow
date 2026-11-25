class AgentRuleLeavesNoApprover(Exception):
    """Nobody could approve tool calls with the rule, so no held run could resume."""
