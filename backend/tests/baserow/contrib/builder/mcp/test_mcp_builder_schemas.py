"""What the builder tools accept over MCP: no Kuma-only parameters."""

import json
import os
import subprocess
import sys

from django.apps import apps

from baserow.core.mcp.groups import GROUP_BUILDER_EDIT, GROUP_BUILDER_READ
from baserow.core.mcp.registries import mcp_tool_registry

KUMA_ONLY_PARAMETERS = {
    "known_refs",
    "known_data_source_refs",
    "defer_required_formulas",
    "options",
}

BUILDER_TOOLS = {
    "list_builders",
    "list_pages",
    "list_data_sources",
    "list_elements",
    "list_element_actions",
    "create_builder",
    "update_builder",
    "create_pages",
    "update_page",
    "create_data_sources",
    "update_data_source",
    "create_display_elements",
    "create_layout_elements",
    "create_form_elements",
    "create_collection_elements",
    "update_element",
    "update_element_style",
    "move_elements",
    "create_element_actions",
    "update_element_action",
    "setup_page",
    "set_theme",
}
# Registered by enterprise, which has the login form it sets up.
ENTERPRISE_BUILDER_TOOLS = {"setup_user_source"}


def _keys(node):
    """Every key used anywhere in a JSON schema."""

    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from _keys(value)


def _builder_tools():
    return [
        tool
        for tool in mcp_tool_registry.get_all()
        if tool.group in (GROUP_BUILDER_READ, GROUP_BUILDER_EDIT)
    ]


def test_builder_tools_are_registered():
    names = {tool.name for tool in _builder_tools()}

    if apps.is_installed("baserow_enterprise"):
        assert names == BUILDER_TOOLS | ENTERPRISE_BUILDER_TOOLS
    else:
        assert names == BUILDER_TOOLS


def test_an_instance_without_the_paid_editions_has_the_builder_tools():
    code = """
import json

import django

django.setup()

from django.apps import apps

from baserow.core.mcp.groups import GROUP_BUILDER_EDIT, GROUP_BUILDER_READ
from baserow.core.mcp.registries import mcp_tool_registry

print(json.dumps({
    "enterprise": apps.is_installed("baserow_enterprise"),
    "tools": sorted(
        tool.name
        for tool in mcp_tool_registry.get_all()
        if tool.group in (GROUP_BUILDER_READ, GROUP_BUILDER_EDIT)
    ),
}))
"""
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(sys.path),
        "DJANGO_SETTINGS_MODULE": "baserow.config.settings.base",
        "BASEROW_OSS_ONLY": "1",
        "SECRET_KEY": os.environ.get("SECRET_KEY") or "test",
    }

    finished = subprocess.run(  # noqa: S603 - only the current interpreter runs fixed test code.
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    listed = json.loads(finished.stdout.strip().splitlines()[-1])
    assert listed["enterprise"] is False
    assert set(listed["tools"]) == BUILDER_TOOLS


def test_no_builder_tool_offers_a_kuma_only_parameter():
    for tool in _builder_tools():
        schema = tool.input_schema.model_json_schema()
        leaked = KUMA_ONLY_PARAMETERS & set(_keys(schema))
        assert not leaked, f"{tool.name} offers {sorted(leaked)}"
