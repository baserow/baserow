"""Kuma-core eval dataset: workspace-level database/automation actions."""

from __future__ import annotations

from baserow.contrib.automation.models import Automation
from baserow.contrib.database.models import Database
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.evals.harness import tool_called
from baserow_enterprise.assistant.evals.registry import (
    register_case,
    register_scenario,
)
from baserow_enterprise.assistant.evals.scenarios import build_database_ui_context
from baserow_enterprise.assistant.evals.types import (
    CheckResult,
    EvalCase,
    EvalRunOutput,
    EvalScenario,
)

PROMPT_LISTS_DATABASES = "What databases do I have in this workspace?"

PROMPT_CREATES_DATABASE = "Create a new database called 'Customer Portal'"

PROMPT_CREATES_AUTOMATION = "Create an empty automation called 'Overdue Task Reminder'."


@register_scenario("core-lists-databases")
def _lists_databases_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace, name="Inventory")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database),
        refs={"database": database},
    )


def _check_lists_databases(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    return [
        CheckResult("called list_builders", tool_called(output, "list_builders") >= 1),
        CheckResult(
            "answer mentions 'Inventory'",
            "inventory" in output.answer.lower(),
            hint=output.answer[:200],
        ),
    ]


register_case(
    EvalCase(
        id="core/lists-databases",
        dataset="kuma-core",
        prompt=PROMPT_LISTS_DATABASES,
        scenario="core-lists-databases",
        checks=_check_lists_databases,
        max_iters=10,
    )
)


@register_scenario("core-creates-database")
def _creates_database_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace)
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database),
        refs={"database": database},
    )


def _check_creates_database(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    created = Database.objects.filter(
        workspace=scenario.workspace, name__icontains="customer"
    )
    return [
        CheckResult(
            "called create_builders", tool_called(output, "create_builders") >= 1
        ),
        CheckResult(
            "database 'Customer Portal' exists",
            created.exists(),
            hint=(
                "databases: "
                f"{list(Database.objects.filter(workspace=scenario.workspace).values_list('name', flat=True))}"
            ),
        ),
    ]


register_case(
    EvalCase(
        id="core/creates-database",
        dataset="kuma-core",
        prompt=PROMPT_CREATES_DATABASE,
        scenario="core-creates-database",
        checks=_check_creates_database,
        max_iters=15,
    )
)


@register_scenario("core-creates-automation")
def _creates_automation_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    fx.create_database_application(workspace=workspace)
    # database is intentionally left out of ui_context, matching the legacy eval.
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace),
    )


def _check_creates_automation(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    created = list(Automation.objects.filter(workspace=scenario.workspace))
    automation = created[0] if created else None
    return [
        CheckResult(
            "called create_builders", tool_called(output, "create_builders") >= 1
        ),
        CheckResult(
            "exactly 1 automation created",
            len(created) == 1,
            hint=f"found {len(created)}: {[a.name for a in created]}",
        ),
        CheckResult(
            "automation named 'Overdue Task Reminder'",
            automation is not None and "overdue" in automation.name.lower(),
            hint=f"got: '{automation.name if automation else None}'",
        ),
        CheckResult(
            "automation in correct workspace",
            automation is not None and automation.workspace_id == scenario.workspace.id,
            hint=(
                f"workspace_id={automation.workspace_id if automation else None} "
                f"vs {scenario.workspace.id}"
            ),
        ),
        CheckResult(
            "automation has no workflows",
            automation is not None and automation.workflows.count() == 0,
            hint=f"workflows: {list(automation.workflows.all()) if automation else []}",
        ),
    ]


register_case(
    EvalCase(
        id="core/creates-automation",
        dataset="kuma-core",
        prompt=PROMPT_CREATES_AUTOMATION,
        scenario="core-creates-automation",
        checks=_check_creates_automation,
        max_iters=15,
        max_tool_errors=1,
    )
)
