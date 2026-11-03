from baserow.core.mcp.groups import GROUP_BUILDER_EDIT, GROUP_BUILDER_READ
from baserow.core.mcp.registries import FunctionMCPTool
from baserow_enterprise.builder.tools import elements


class ListElementsMcpTool(FunctionMCPTool):
    type = "list_elements"
    group = GROUP_BUILDER_READ
    title = "List elements"
    read_only = True
    function = elements.list_elements


class CreateDisplayElementsMcpTool(FunctionMCPTool):
    type = "create_display_elements"
    group = GROUP_BUILDER_EDIT
    title = "Create display elements"
    read_only = False
    destructive = False
    function = elements.create_display_elements


class CreateLayoutElementsMcpTool(FunctionMCPTool):
    type = "create_layout_elements"
    group = GROUP_BUILDER_EDIT
    title = "Create layout elements"
    read_only = False
    destructive = False
    function = elements.create_layout_elements


class CreateFormElementsMcpTool(FunctionMCPTool):
    type = "create_form_elements"
    group = GROUP_BUILDER_EDIT
    title = "Create form elements"
    read_only = False
    destructive = False
    function = elements.create_form_elements


class CreateCollectionElementsMcpTool(FunctionMCPTool):
    type = "create_collection_elements"
    group = GROUP_BUILDER_EDIT
    title = "Create collection elements"
    read_only = False
    destructive = False
    function = elements.create_collection_elements


class UpdateElementMcpTool(FunctionMCPTool):
    type = "update_element"
    group = GROUP_BUILDER_EDIT
    title = "Update an element"
    read_only = False
    destructive = False
    function = elements.update_element


class UpdateElementStyleMcpTool(FunctionMCPTool):
    type = "update_element_style"
    group = GROUP_BUILDER_EDIT
    title = "Update an element's style"
    read_only = False
    destructive = False
    function = elements.update_element_style


class MoveElementsMcpTool(FunctionMCPTool):
    type = "move_elements"
    group = GROUP_BUILDER_EDIT
    title = "Move elements"
    read_only = False
    destructive = False
    function = elements.move_elements
