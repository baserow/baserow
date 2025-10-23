"""
Test that dspy is lazy-loaded only when the Assistant is actually used.

This prevents unnecessary memory usage when the AI Assistant feature is not being used.
"""
import sys

import pytest


@pytest.mark.django_db
class TestDspyLazyLoading:
    """Verify that dspy is only loaded when Assistant is instantiated."""

    def test_dspy_not_loaded_on_django_startup(self):
        """
        Test that dspy is NOT loaded when Django starts up.

        This is critical for memory efficiency - dspy should only be loaded
        when the AI Assistant feature is actually used.
        """

        # Remove dspy and litellm from sys.modules if already loaded
        # (this can happen if other tests ran first)
        modules_to_remove = [
            key
            for key in sys.modules
            if key.startswith("dspy") or key.startswith("litellm")
        ]
        for module in modules_to_remove:
            del sys.modules[module]

        # Import the handler module (which is what gets imported at Django startup)
        from baserow_enterprise.assistant import handler  # noqa: F401

        # Verify dspy and litellm are NOT loaded yet
        assert "dspy" not in sys.modules, (
            "dspy should not be loaded on import. "
            "Check for top-level dspy imports in assistant module files."
        )

        assert "litellm" not in sys.modules, (
            "litellm should not be loaded on import. "
            "Check for top-level litellm imports in assistant module files."
        )

    def test_dspy_loaded_when_assistant_created(
        self, data_fixture, enterprise_data_fixture
    ):
        """
        Test that dspy IS loaded when an Assistant object is created.

        This verifies that lazy loading works correctly and dspy is available
        when needed.
        """

        # Remove dspy and litellm from sys.modules to start fresh
        modules_to_remove = [
            key
            for key in sys.modules
            if key.startswith("dspy") or key.startswith("litellm")
        ]
        for module in modules_to_remove:
            del sys.modules[module]

        # Create necessary fixtures
        user = data_fixture.create_user()
        workspace = data_fixture.create_workspace(user=user)
        enterprise_data_fixture.enable_enterprise()

        # Import and use handler (should not load dspy yet)
        from baserow_enterprise.assistant.handler import AssistantHandler
        from baserow_enterprise.assistant.models import AssistantChat

        # Verify dspy and litellm are still not loaded
        assert (
            "dspy" not in sys.modules
        ), "dspy should not be loaded after importing handler"

        assert (
            "litellm" not in sys.modules
        ), "litellm should not be loaded after importing handler"

        # Create a chat
        chat = AssistantChat.objects.create(
            user=user,
            workspace=workspace,
        )

        # Create Assistant - this SHOULD trigger dspy loading
        handler = AssistantHandler()
        assistant = handler.get_assistant(chat)

        # Now dspy and litellm  should be loaded
        assert "dspy" in sys.modules, (
            "dspy should be loaded after creating Assistant instance. "
            "Check that Assistant.__init__ imports dspy."
        )

        assert "litellm" in sys.modules, (
            "litellm should be loaded after creating Assistant instance. "
            "Check that Assistant.__init__ imports dspy."
        )

        assert assistant is not None

    def test_assistant_handler_does_not_load_dspy(self, data_fixture):
        """
        Test that using AssistantHandler methods (other than get_assistant)
        does not load dspy.
        """

        # Remove dspy and litellm from sys.modules
        modules_to_remove = [
            key
            for key in sys.modules
            if key.startswith("dspy") or key.startswith("litellm")
        ]
        for module in modules_to_remove:
            del sys.modules[module]

        # Create fixtures
        user = data_fixture.create_user()
        workspace = data_fixture.create_workspace(user=user)

        from baserow_enterprise.assistant.handler import AssistantHandler

        handler = AssistantHandler()

        # These operations should not load dspy
        chats = handler.list_chats(user, workspace.id)
        assert chats is not None

        # Verify dspy and litellm are still not loaded
        assert "dspy" not in sys.modules, (
            "dspy should not be loaded by AssistantHandler methods "
            "(except get_assistant)"
        )

        assert "litellm" not in sys.modules, (
            "litellm should not be loaded by AssistantHandler methods "
            "(except get_assistant)"
        )
