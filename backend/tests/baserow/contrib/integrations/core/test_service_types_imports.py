import ast
from pathlib import Path

from baserow.contrib.integrations.core import service_types


def test_integrations_core_service_types_has_no_module_level_automation_import():
    """
    Trigger service types are hosted by Automation nodes and by agent triggers.
    A module-level import of `baserow.contrib.automation` would make every host
    depend on Automation, so only the Automation package may know Automation's
    exceptions. The `TYPE_CHECKING` block and function-level imports are
    statements nested in `tree.body` entries, not entries themselves, so they
    are not covered here.
    """

    tree = ast.parse(Path(service_types.__file__).read_text())
    module_level_automation_imports = [
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and (node.module or "").startswith("baserow.contrib.automation")
    ]
    assert module_level_automation_imports == []
