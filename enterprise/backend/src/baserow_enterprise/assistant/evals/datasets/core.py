"""Kuma-core eval dataset: workspace-level database/automation actions."""

from __future__ import annotations

import re
from datetime import timedelta

from django.utils import timezone

from baserow.contrib.automation.models import Automation
from baserow.contrib.builder.models import Builder
from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.database.models import Database
from baserow.contrib.database.search.handler import SearchHandler
from baserow.core.models import Application
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.deps import AgentMode
from baserow_enterprise.assistant.evals.harness import tool_called
from baserow_enterprise.assistant.evals.registry import (
    register_case,
    register_scenario,
)
from baserow_enterprise.assistant.evals.scenarios import (
    build_builder_ui_context,
    build_database_ui_context,
)
from baserow_enterprise.assistant.evals.types import (
    CheckResult,
    EvalCase,
    EvalRunOutput,
    EvalScenario,
)

PROMPT_LISTS_DATABASES = "What databases do I have in this workspace?"

PROMPT_CREATES_DATABASE = "Create a new database called 'Customer Portal'"

PROMPT_CREATES_AUTOMATION = "Create an empty automation called 'Overdue Task Reminder'."

PROMPT_CREATES_APPLICATION = "create a new application website"

PROMPT_CREATES_DASHBOARD = "Create a dashboard called 'Sales Overview'."

PROMPT_CREATES_SEVERAL_APPLICATIONS = (
    "Create a database called 'Inventory', an automation called 'Stock Alerts' "
    "and a dashboard called 'Stock Overview'."
)

PROMPT_RENAMES_AUTOMATION = "Rename the automation 'Order Flow' to 'Order Pipeline'."


PROMPT_SEARCH_FINDS_ROW = "Find the customer called Acme."

PROMPT_SEARCH_FINDS_TABLE = "Which table has the invoices?"


@register_scenario("core-search-workspace")
def _search_workspace_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    other = fx.create_database_application(workspace=workspace, name="Operations")
    fx.create_database_table(database=other, name="Tasks")
    database = fx.create_database_application(workspace=workspace, name="Sales")
    customers, _, rows = fx.build_table(
        user=user,
        database=database,
        name="Customers",
        columns=[("Name", {"type": "text", "primary": True})],
        rows=[["Globex"], ["Acme"]],
    )
    invoices = fx.create_database_table(database=database, name="Invoices")
    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
    SearchHandler.initialize_missing_search_data(customers)
    SearchHandler.process_search_data_updates(customers)
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, other),
        refs={"customers": customers, "invoices": invoices, "acme": rows[1]},
    )


def _check_search_finds_row(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    answer = output.answer.lower()
    return [
        CheckResult(
            "called search_workspace", tool_called(output, "search_workspace") >= 1
        ),
        CheckResult("answer mentions Acme", "acme" in answer, hint=output.answer[:200]),
        CheckResult(
            "answer mentions Customers", "customers" in answer, hint=output.answer[:200]
        ),
    ]


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")

# Clauses are judged apart, so "in Sales, not Operations" doesn't deny the table.
_CLAUSE_END = re.compile(r"[,;()—–]|\s-\s|\bbut\b")

_NEGATION = re.compile(
    r"\b(?:no|not|none|never|nothing|nowhere|without|cannot)\b|n't\b"
)

# Said after the table is named: "the Invoices table is missing".
_ABSENT = re.compile(r"\b(?:missing|absent|not found)\b")

_BULLET = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+")

# The other database of the scenario. "Not in Operations" contrasts, it doesn't deny.
_OTHER_DATABASES = ("operations",)
_CONTRAST = re.compile(
    r"\bnot\s+(?:in\s+|from\s+|under\s+)?(?:the\s+)?(?:%s)\b"
    % "|".join(_OTHER_DATABASES)
)

_CREATE_OFFERS = (
    "create it",
    "create one",
    "create an invoices",
    "create a new invoices",
    "create the invoices",
    "create a table",
    "create a new table",
)


def _normalized(answer: str) -> str:
    # Models often write a typographic apostrophe, and markdown around names.
    text = answer.lower().replace("’", "'")
    return re.sub(r"\*\*|__|`", "", text)


def _denies_invoices(clause: str) -> bool:
    """
    Whether a clause says the Invoices table isn't there: a negation before the
    name, or one or an absence word after it. A clause about another database only
    ("Operations has no invoices table") doesn't count.
    """

    clause = _CONTRAST.sub("", clause)
    at = clause.find("invoice")
    if at == -1:
        return False
    if any(name in clause for name in _OTHER_DATABASES) and "sales" not in clause:
        return False
    before, after = clause[:at], clause[at:]
    return bool(
        _NEGATION.search(before) or _NEGATION.search(after) or _ABSENT.search(after)
    )


def _clauses(text: str) -> list[str]:
    return [
        clause
        for sentence in _SENTENCE_END.split(text)
        for clause in _CLAUSE_END.split(sentence)
    ]


def _listed_under_sales(text: str) -> bool:
    """Whether a line naming Sales is followed by a list with Invoices in it."""

    lines = text.split("\n")
    for index, line in enumerate(lines):
        if "sales" not in line or _BULLET.match(line):
            continue
        for item in lines[index + 1 :]:
            if not item.strip():
                continue
            if not _BULLET.match(item):
                break
            if "invoice" in item and not _denies_invoices(item):
                return True
    return False


def _places_invoices_in_sales(text: str) -> bool:
    """
    Whether a sentence names Sales and Invoices without denying the table, or a
    list of Sales has it.
    """

    for sentence in _SENTENCE_END.split(text):
        if "sales" in sentence and "invoices" in sentence:
            if not any(_denies_invoices(c) for c in _CLAUSE_END.split(sentence)):
                return True
    return _listed_under_sales(text)


def _check_search_finds_table(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    text = _normalized(output.answer)
    return [
        CheckResult(
            "called search_workspace or list_tables",
            tool_called(output, "search_workspace") + tool_called(output, "list_tables")
            >= 1,
        ),
        CheckResult(
            "the answer places the Invoices table in Sales",
            _places_invoices_in_sales(text),
            hint=output.answer[:200],
        ),
        CheckResult(
            "no part of the answer denies the Invoices table",
            not any(_denies_invoices(clause) for clause in _clauses(text)),
            hint=output.answer[:200],
        ),
        CheckResult(
            "answer doesn't offer to create it",
            not any(offer in text for offer in _CREATE_OFFERS),
            hint=output.answer[:200],
        ),
    ]


register_case(
    EvalCase(
        id="core/search-finds-row",
        dataset="kuma-core",
        prompt=PROMPT_SEARCH_FINDS_ROW,
        scenario="core-search-workspace",
        checks=_check_search_finds_row,
        max_iters=10,
    )
)
register_case(
    EvalCase(
        id="core/search-finds-table",
        dataset="kuma-core",
        prompt=PROMPT_SEARCH_FINDS_TABLE,
        scenario="core-search-workspace",
        checks=_check_search_finds_table,
        max_iters=10,
    )
)


PROMPT_AUDIT_LOG_WHO_DELETED = "Who deleted a table this week?"

PROMPT_AUDIT_LOG_WHAT_CHANGED = "What did Anna change yesterday?"


def _enable_enterprise() -> None:
    """
    Give the instance the enterprise licence of the enterprise tests. The eval
    database is disposable and runs with the debug licence key, which that licence is
    signed for.
    """

    from baserow_enterprise_tests.enterprise_fixtures import EnterpriseFixtures

    EnterpriseFixtures().enable_enterprise()


@register_scenario("core-audit-log")
def _audit_log_scenario(fx: Fixtures) -> EvalScenario:
    from baserow_enterprise.audit_log.models import AuditLogEntry

    # The audit log only keeps the email. A case's rounds share a database, so it
    # has to be another one each time.
    user = fx.create_user(first_name="Sam", email=f"sam.{fx.fake.uuid4()}@example.com")
    anna = fx.create_user(
        first_name="Anna", email=f"anna.{fx.fake.uuid4()}@example.com"
    )
    _enable_enterprise()
    workspace = fx.create_workspace(user=user)
    fx.create_user_workspace(user=anna, workspace=workspace)
    database = fx.create_database_application(workspace=workspace, name="Sales")

    def entry(actor, days_ago, action_type, short, long, params):
        AuditLogEntry.objects.create(
            workspace_id=workspace.id,
            workspace_name=workspace.name,
            actor_id=actor.id,
            actor_name=actor.email,
            action_type=action_type,
            action_timestamp=timezone.now() - timedelta(days=days_ago),
            action_params=params,
            original_action_short_descr=short,
            original_action_long_descr=long,
        )

    entry(
        anna,
        1,
        "update_table",
        "Update table",
        'Table "%(table_name)s" updated',
        {"table_name": "Renewals"},
    )
    # Today, so it's in "this week" on any day of the week.
    entry(
        user,
        0,
        "delete_table",
        "Delete table",
        'Table "%(table_name)s" deleted',
        {"table_name": "Old leads"},
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database),
        refs={},
    )


def _called_the_audit_log(output: EvalRunOutput) -> CheckResult:
    return CheckResult(
        "called list_audit_log",
        tool_called(output, "list_audit_log") >= 1,
    )


def _check_audit_log_who_deleted(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    return [
        _called_the_audit_log(output),
        CheckResult(
            "answer names who deleted it",
            "sam" in output.answer.lower(),
            hint=output.answer[:200],
        ),
    ]


def _check_audit_log_what_changed(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    return [
        _called_the_audit_log(output),
        CheckResult(
            "answer names the table Anna changed",
            "renewals" in output.answer.lower(),
            hint=output.answer[:200],
        ),
    ]


register_case(
    EvalCase(
        id="core/audit-log-who-deleted",
        dataset="kuma-core",
        prompt=PROMPT_AUDIT_LOG_WHO_DELETED,
        scenario="core-audit-log",
        checks=_check_audit_log_who_deleted,
        max_iters=10,
    )
)
register_case(
    EvalCase(
        id="core/audit-log-what-changed",
        dataset="kuma-core",
        prompt=PROMPT_AUDIT_LOG_WHAT_CHANGED,
        scenario="core-audit-log",
        checks=_check_audit_log_what_changed,
        max_iters=10,
    )
)


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


@register_scenario("core-one-database")
def _one_database_scenario(fx: Fixtures) -> EvalScenario:
    """A workspace with one empty database, open in the UI."""

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
            "called create_database", tool_called(output, "create_database") >= 1
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
        scenario="core-one-database",
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
            "called create_automation", tool_called(output, "create_automation") >= 1
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


def _check_creates_application(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    workspace = scenario.workspace
    builders = list(Builder.objects.filter(workspace=workspace))
    # The scenario starts with one database and nothing else.
    databases = Database.objects.filter(workspace=workspace).count()
    automations = Automation.objects.filter(workspace=workspace).count()
    dashboards = Dashboard.objects.filter(workspace=workspace).count()
    return [
        CheckResult(
            "called create_builder", tool_called(output, "create_builder") >= 1
        ),
        CheckResult(
            "a new application builder exists",
            len(builders) == 1,
            hint=f"found {len(builders)}: {[b.name for b in builders]}",
        ),
        CheckResult(
            "no database, automation or dashboard created",
            databases == 1 and automations == 0 and dashboards == 0,
            hint=(
                f"databases={databases}, automations={automations}, "
                f"dashboards={dashboards}; tools called: {output.tool_calls}"
            ),
        ),
    ]


register_case(
    EvalCase(
        id="core/creates-application",
        dataset="kuma-core",
        # A bare request for an application is a builder, made without asking.
        prompt=PROMPT_CREATES_APPLICATION,
        scenario="core-one-database",
        checks=_check_creates_application,
        max_iters=15,
    )
)


def _named(model, workspace, name: str) -> list:
    return [
        application
        for application in model.objects.filter(workspace=workspace)
        if application.name.strip().casefold() == name.casefold()
    ]


def _check_creates_dashboard(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    workspace = scenario.workspace
    dashboards = list(Dashboard.objects.filter(workspace=workspace))
    applications = [
        application.name
        for application in Application.objects.filter(workspace=workspace)
    ]
    return [
        CheckResult(
            "called create_dashboard", tool_called(output, "create_dashboard") >= 1
        ),
        CheckResult(
            "exactly one dashboard, named Sales Overview",
            len(dashboards) == 1
            and len(_named(Dashboard, workspace, "Sales Overview")) == 1,
            hint=f"found {len(dashboards)}: {[d.name for d in dashboards]}",
        ),
        CheckResult(
            "no application builder created",
            not Builder.objects.filter(workspace=workspace).exists(),
            hint=f"tools called: {output.tool_calls}",
        ),
        CheckResult(
            "databases unchanged",
            Database.objects.filter(workspace=workspace).count() == 1,
        ),
        CheckResult(
            "no other application created",
            len(applications) == 2,
            hint=f"applications: {applications}",
        ),
    ]


register_case(
    EvalCase(
        id="core/creates-dashboard",
        dataset="kuma-core",
        prompt=PROMPT_CREATES_DASHBOARD,
        scenario="core-one-database",
        checks=_check_creates_dashboard,
        max_iters=15,
    )
)


@register_scenario("core-creates-several-applications")
def _creates_several_applications_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(user=user, workspace=workspace, name="Shop")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={"builder": builder},
    )


def _check_creates_several_applications(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    workspace = scenario.workspace
    wanted = (
        ("create_database", Database, "Inventory"),
        ("create_automation", Automation, "Stock Alerts"),
        ("create_dashboard", Dashboard, "Stock Overview"),
    )
    checks = []
    for tool, model, name in wanted:
        checks.append(
            CheckResult(
                f"called {tool}",
                tool_called(output, tool) >= 1,
                hint=f"tools called: {output.tool_calls}",
            )
        )
        checks.append(
            CheckResult(
                f"exactly one {model.__name__.lower()} named '{name}'",
                len(_named(model, workspace, name)) == 1,
                hint=(
                    "found "
                    f"{[a.name for a in model.objects.filter(workspace=workspace)]}"
                ),
            )
        )
    builders = list(Builder.objects.filter(workspace=workspace))
    checks.append(
        CheckResult(
            "no application builder added",
            len(builders) == 1,
            hint=f"builders: {[b.name for b in builders]}",
        )
    )
    # The Shop builder and the three new applications, nothing else.
    applications = [
        application.name
        for application in Application.objects.filter(workspace=workspace)
    ]
    checks.append(
        CheckResult(
            "no other application created",
            len(applications) == 4,
            hint=f"applications: {applications}",
        )
    )
    return checks


register_case(
    EvalCase(
        id="core/creates-several-applications",
        dataset="kuma-core",
        prompt=PROMPT_CREATES_SEVERAL_APPLICATIONS,
        scenario="core-creates-several-applications",
        checks=_check_creates_several_applications,
        mode=AgentMode.APPLICATION,
        max_iters=20,
        max_tool_errors=1,
    )
)


@register_scenario("core-renames-automation")
def _renames_automation_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace, name="Sales")
    automation = fx.create_automation_application(
        user=user, workspace=workspace, name="Order Flow"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database),
        refs={"database": database, "automation": automation},
        pre_state={
            "applications": Application.objects.filter(workspace=workspace).count()
        },
    )


def _check_renames_automation(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    automation = scenario.refs["automation"]
    automation.refresh_from_db()
    database = scenario.refs["database"]
    database.refresh_from_db()
    return [
        CheckResult(
            "called update_automation", tool_called(output, "update_automation") >= 1
        ),
        CheckResult(
            "automation renamed to Order Pipeline",
            automation.name.strip().casefold() == "order pipeline",
            hint=f"name: '{automation.name}'",
        ),
        CheckResult(
            "database name unchanged",
            database.name == "Sales",
            hint=f"name: '{database.name}'",
        ),
        CheckResult(
            "no new application",
            Application.objects.filter(workspace=scenario.workspace).count()
            == scenario.pre_state["applications"],
            hint=f"tools called: {output.tool_calls}",
        ),
    ]


register_case(
    EvalCase(
        id="core/renames-automation",
        dataset="kuma-core",
        prompt=PROMPT_RENAMES_AUTOMATION,
        scenario="core-renames-automation",
        checks=_check_renames_automation,
        max_iters=15,
        max_tool_errors=1,
    )
)
