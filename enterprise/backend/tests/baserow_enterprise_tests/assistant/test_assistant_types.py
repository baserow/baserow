from baserow_enterprise.assistant.types import (
    ApplicationUIContext,
    HumanMessage,
    TableUIContext,
    UIContext,
    ViewUIContext,
    WorkspaceUIContext,
)


class TestUIContext:
    """Tests for UIContext formatting."""

    def test_ui_context_with_workspace_only(self):
        """Test UIContext formatting with only workspace."""

        workspace = WorkspaceUIContext(id=1, name="My Workspace")
        context = UIContext(workspace=workspace)

        expected = """<workspace>
• Id: 1
• Name: My Workspace
</workspace>
"""
        assert str(context) == expected.strip()
        assert context._format_ui_context() == expected.strip()

    def test_ui_context_with_workspace_and_application(self):
        """Test UIContext formatting with workspace and application."""

        workspace = WorkspaceUIContext(id=1, name="My Workspace")
        application = ApplicationUIContext(id="app123", name="My App", type="database")
        context = UIContext(workspace=workspace, application=application)

        expected = """<workspace>
• Id: 1
• Name: My Workspace
</workspace>

<application>
• Id: app123
• Name: My App
• Type: database
</application>
"""
        assert str(context) == expected.strip()

    def test_ui_context_with_workspace_application_and_table(self):
        """Test UIContext formatting with workspace, application, and table."""

        workspace = WorkspaceUIContext(id=1, name="My Workspace")
        application = ApplicationUIContext(id="app123", name="My App", type="database")
        table = TableUIContext(id=42, name="Users Table")
        context = UIContext(workspace=workspace, application=application, table=table)

        expected = """<workspace>
• Id: 1
• Name: My Workspace
</workspace>

<application>
• Id: app123
• Name: My App
• Type: database
</application>

<table>
• Id: 42
• Name: Users Table
</table>
"""
        assert str(context) == expected.strip()

    def test_ui_context_with_all_components(self):
        """Test UIContext formatting with all components including view."""

        workspace = WorkspaceUIContext(id=1, name="My Workspace")
        application = ApplicationUIContext(id="app123", name="My App", type="database")
        table = TableUIContext(id=42, name="Users Table")
        view = ViewUIContext(id=7, name="Grid View", type="grid")
        context = UIContext(
            workspace=workspace, application=application, table=table, view=view
        )

        expected = """<workspace>
• Id: 1
• Name: My Workspace
</workspace>

<application>
• Id: app123
• Name: My App
• Type: database
</application>

<table>
• Id: 42
• Name: Users Table
</table>

<view>
• Id: 7
• Name: Grid View
• Type: grid
</view>
"""
        assert str(context) == expected.strip()

    def test_ui_context_with_special_characters_in_names(self):
        """Test UIContext formatting with special characters in names."""

        workspace = WorkspaceUIContext(id=1, name='My <Workspace> & "Team"')
        application = ApplicationUIContext(
            id="app-456", name="App's Name (Beta)", type="database"
        )
        context = UIContext(workspace=workspace, application=application)

        expected = """<workspace>
• Id: 1
• Name: My <Workspace> & "Team"
</workspace>

<application>
• Id: app-456
• Name: App's Name (Beta)
• Type: database
</application>
"""
        assert str(context) == expected.strip()

    def test_ui_context_with_timezone(self):
        """Test UIContext with custom timezone."""

        workspace = WorkspaceUIContext(id=1, name="My Workspace")
        context = UIContext(workspace=workspace, timezone="Europe/Amsterdam")

        # Timezone should be stored but not included in the formatted output
        assert context.timezone == "Europe/Amsterdam"

        expected = """<workspace>
• Id: 1
• Name: My Workspace
</workspace>
"""
        assert str(context) == expected.strip()

    def test_ui_context_default_timezone(self):
        """Test UIContext default timezone is UTC."""

        workspace = WorkspaceUIContext(id=1, name="My Workspace")
        context = UIContext(workspace=workspace)

        assert context.timezone == "UTC"

    def test_ui_context_skips_none_components(self):
        """Test that UIContext correctly skips None components."""

        workspace = WorkspaceUIContext(id=1, name="My Workspace")
        table = TableUIContext(id=42, name="Users Table")
        # Intentionally skip application but include table
        context = UIContext(
            workspace=workspace, application=None, table=table  # Explicitly None
        )

        expected = """<workspace>
• Id: 1
• Name: My Workspace
</workspace>

<table>
• Id: 42
• Name: Users Table
</table>
"""
        assert str(context) == expected.strip()

    def test_format_ui_context_section_empty_content(self):
        """Test _format_ui_context_section with empty content."""

        workspace = WorkspaceUIContext(id=1, name="My Workspace")
        context = UIContext(workspace=workspace)

        result = context._format_ui_context_section("test")
        assert result == ""

    def test_human_message_with_ui_context(self):
        """Test HumanMessage can include UIContext."""

        workspace = WorkspaceUIContext(id=1, name="My Workspace")
        ui_context = UIContext(workspace=workspace)

        message = HumanMessage(content="Hello, AI!", ui_context=ui_context)

        assert message.ui_context == ui_context
        assert message.content == "Hello, AI!"
        assert message.type == "human"
        assert message.id is not None  # Should be auto-generated

    def test_human_message_without_ui_context(self):
        """Test HumanMessage without UIContext."""

        message = HumanMessage(content="Hello, AI!")

        assert message.ui_context is None
        assert message.content == "Hello, AI!"

    def test_ui_context_components_have_correct_types(self):
        """Test that UIContext components have correct types."""

        workspace = WorkspaceUIContext(id=1, name="Workspace")
        application = ApplicationUIContext(id="app1", name="App", type="database")
        table = TableUIContext(id=2, name="Table")
        view = ViewUIContext(id=3, name="View", type="grid")

        context = UIContext(
            workspace=workspace, application=application, table=table, view=view
        )

        assert isinstance(context.workspace, WorkspaceUIContext)
        assert isinstance(context.application, ApplicationUIContext)
        assert isinstance(context.table, TableUIContext)
        assert isinstance(context.view, ViewUIContext)

        # Check required fields
        assert context.workspace.id == 1
        assert context.workspace.name == "Workspace"
        assert context.application.id == "app1"
        assert context.application.type == "database"
        assert context.view.type == "grid"

    def test_ui_context_formatting_consistency(self):
        """Test that __str__ and _format_ui_context produce the same output."""

        workspace = WorkspaceUIContext(id=10, name="Test Workspace")
        application = ApplicationUIContext(id="test", name="Test App", type="database")

        context = UIContext(workspace=workspace, application=application)

        assert str(context) == context._format_ui_context()

    def test_ui_context_with_numeric_and_string_ids(self):
        """Test UIContext handles both numeric and string IDs correctly."""

        workspace = WorkspaceUIContext(id=999, name="Workspace")
        application = ApplicationUIContext(
            id="string-id-123", name="App", type="database"
        )
        table = TableUIContext(id=0, name="Table Zero")  # Edge case: ID of 0
        view = ViewUIContext(id=1000000, name="View", type="kanban")  # Large ID

        context = UIContext(
            workspace=workspace, application=application, table=table, view=view
        )

        formatted = str(context)

        assert "• Id: 999" in formatted
        assert "• Id: string-id-123" in formatted
        assert "• Id: 0" in formatted
        assert "• Id: 1000000" in formatted
