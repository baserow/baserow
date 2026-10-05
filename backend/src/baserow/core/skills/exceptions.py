class WorkspaceSkillDoesNotExist(Exception):
    """Raised when a skill does not exist in the workspace."""


class WorkspaceSkillNameNotUnique(Exception):
    """Raised when another skill of the workspace already has the name."""
