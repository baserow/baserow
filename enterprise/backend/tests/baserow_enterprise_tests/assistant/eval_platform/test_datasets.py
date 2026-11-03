"""Structure-level tests for the kuma-core/database/docs eval datasets.

No LLM calls here: these only check that registration produced the right
shape (case ids, counts, scenario wiring). ``TestScenarioSmoke`` is the one
class that touches the database, to build every scenario once.
"""

import json

import pytest

from baserow.contrib.builder.workflow_actions.models import (
    NotificationWorkflowAction,
    OpenPageWorkflowAction,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.core.formula.types import BaserowFormulaObject
from baserow_enterprise.assistant.deps import AgentMode
from baserow_enterprise.assistant.evals.datasets.core import (
    _check_creates_application,
    _check_creates_automation,
    _creates_application_scenario,
    _creates_automation_scenario,
)
from baserow_enterprise.assistant.evals.registry import (
    all_cases,
    cases_by_dataset,
    get_scenario,
    load_all,
)
from baserow_enterprise.assistant.evals.scenarios import make_fixtures
from baserow_enterprise.assistant.evals.types import EvalCase, EvalRunOutput

load_all()


@pytest.mark.django_db
def test_create_automation_check_ignores_previous_runs(data_fixture):
    case = EvalCase(
        id="core/creates-automation",
        dataset="kuma-core",
        prompt="Create automation",
        scenario="core-creates-automation",
        checks=_check_creates_automation,
    )
    output = EvalRunOutput(
        answer="Created it",
        messages=[],
        tool_calls=["create_automation"],
        tool_error_count=0,
        tool_error_hint="",
        sources=[],
        request_count=1,
        duration_s=0,
    )
    for _ in range(2):
        scenario = _creates_automation_scenario(make_fixtures())
        data_fixture.create_automation_application(
            workspace=scenario.workspace, name="Overdue Task Reminder"
        )
        assert all(check.passed for check in case.checks(case, scenario, output))


def _creates_application_output(tool_calls):
    return EvalRunOutput(
        answer="Done",
        messages=[],
        tool_calls=tool_calls,
        tool_error_count=0,
        tool_error_hint="",
        sources=[],
        request_count=1,
        duration_s=0,
    )


def _creates_application_case():
    return EvalCase(
        id="core/creates-application",
        dataset="kuma-core",
        prompt="create a new application website",
        scenario="core-creates-application",
        checks=_check_creates_application,
    )


@pytest.mark.django_db
def test_create_application_check_passes_for_one_new_builder(data_fixture):
    case = _creates_application_case()
    scenario = _creates_application_scenario(make_fixtures())
    data_fixture.create_builder_application(
        workspace=scenario.workspace, name="Website"
    )

    checks = case.checks(
        case, scenario, _creates_application_output(["create_builder"])
    )

    assert all(check.passed for check in checks), checks


@pytest.mark.django_db
def test_create_application_check_fails_when_a_database_is_made_instead(data_fixture):
    case = _creates_application_case()
    scenario = _creates_application_scenario(make_fixtures())
    data_fixture.create_database_application(workspace=scenario.workspace)

    checks = case.checks(
        case, scenario, _creates_application_output(["create_database"])
    )

    assert {c.name for c in checks if not c.passed} == {
        "called create_builder",
        "a new application builder exists",
        "no database, automation or dashboard created",
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "change,failing_checks",
    [
        ("keep", set()),
        ("recolor", {"existing options preserved"}),
        ("recreate", {"existing options preserved", "row keeps its option"}),
    ],
)
def test_updates_select_options_check_catches_lost_ids_colors_and_cells(
    change, failing_checks
):
    (case,) = [c for c in all_cases() if c.id == "database/updates-select-options"]
    output = EvalRunOutput(
        answer="Added it",
        messages=[],
        tool_calls=["update_fields"],
        tool_error_count=0,
        tool_error_hint="",
        sources=[],
        request_count=1,
        duration_s=0,
    )
    scenario = get_scenario(case.scenario)(make_fixtures())
    existing = []
    for option_id, value, color in scenario.refs["existing_options"]:
        option = {"value": value, "color": "red" if change == "recolor" else color}
        if change != "recreate":
            option["id"] = option_id
        existing.append(option)
    FieldHandler().update_field(
        scenario.user,
        scenario.refs["status_field"],
        select_options=[*existing, {"value": "In Progress", "color": "blue"}],
    )

    checks = case.checks(case, scenario, output)

    assert {check.name for check in checks if not check.passed} == failing_checks


def _failed(case_id, scenario_name, tool_calls, prepare=None):
    """Names of the checks of a case that fail after ``prepare`` changed the data."""

    case = next(c for c in all_cases() if c.id == case_id)
    scenario = get_scenario(scenario_name)(make_fixtures())
    if prepare:
        prepare(scenario)
    checks = case.checks(case, scenario, _creates_application_output(tool_calls))
    return {check.name for check in checks if not check.passed}


@pytest.mark.django_db
def test_creates_dashboard_check_needs_a_dashboard_and_the_right_tool(data_fixture):
    def made(scenario):
        data_fixture.create_dashboard_application(
            workspace=scenario.workspace, name="Sales Overview"
        )

    def wrong(scenario):
        data_fixture.create_builder_application(
            workspace=scenario.workspace, name="Sales Overview"
        )

    args = ("core/creates-dashboard", "core-creates-dashboard")

    assert _failed(*args, ["create_dashboard"], made) == set()
    assert _failed(*args, ["create_builder"], wrong) == {
        "called create_dashboard",
        "exactly one dashboard, named Sales Overview",
        "no application builder created",
    }


@pytest.mark.django_db
def test_creates_several_applications_check_needs_one_of_each(data_fixture):
    def made(scenario, dashboard=True):
        workspace = scenario.workspace
        data_fixture.create_database_application(workspace=workspace, name="Inventory")
        data_fixture.create_automation_application(
            workspace=workspace, name="Stock Alerts"
        )
        if dashboard:
            data_fixture.create_dashboard_application(
                workspace=workspace, name="Stock Overview"
            )
        else:
            data_fixture.create_builder_application(
                workspace=workspace, name="Stock Overview"
            )

    args = ("core/creates-several-applications", "core-creates-several-applications")
    tools = ["create_database", "create_automation", "create_dashboard"]

    assert _failed(*args, tools, made) == set()
    assert _failed(
        *args,
        ["create_database", "create_automation", "create_builder"],
        lambda scenario: made(scenario, dashboard=False),
    ) == {
        "called create_dashboard",
        "exactly one dashboard named 'Stock Overview'",
        "no application builder added",
    }


@pytest.mark.django_db
def test_renames_automation_check_needs_the_automation_renamed(data_fixture):
    def renamed(scenario):
        automation = scenario.refs["automation"]
        automation.name = "Order Pipeline"
        automation.save()

    def recreated(scenario):
        data_fixture.create_automation_application(
            workspace=scenario.workspace, name="Order Pipeline"
        )

    args = ("core/renames-automation", "core-renames-automation")

    assert _failed(*args, ["update_automation"], renamed) == set()
    assert _failed(*args, ["create_automation"], recreated) == {
        "called update_automation",
        "automation renamed to Order Pipeline",
        "no new application",
    }


@pytest.mark.django_db
def test_changes_notification_title_check_needs_the_same_action_updated(data_fixture):
    def updated(scenario):
        action = NotificationWorkflowAction.objects.get(
            id=scenario.refs["save_action_id"]
        )
        action.title = "'All done!'"
        action.save()

    def added(scenario):
        data_fixture.create_notification_workflow_action(
            page=scenario.refs["save_button"].page,
            element=scenario.refs["save_button"],
            event="click",
            title="'All done!'",
        )

    args = ("builder/changes-notification-title", "builder-changes-actions")

    assert _failed(*args, ["update_action"], updated) == set()
    assert _failed(*args, ["create_actions"], added) == {
        "called update_action",
        "Save button still has one action, the same one",
        "message is 'All done!'",
    }


@pytest.mark.django_db
def test_changes_open_page_parameter_check_needs_slug_changed_and_id_kept(
    data_fixture,
):
    def set_parameters(slug, id_value="'42'"):
        def prepare(scenario):
            action = OpenPageWorkflowAction.objects.get(
                id=scenario.refs["open_action_id"]
            )
            action.page_parameters = [
                {"name": "id", "value": BaserowFormulaObject.create(id_value)},
                {"name": "slug", "value": BaserowFormulaObject.create(slug)},
            ]
            action.save()

        return prepare

    args = ("builder/changes-open-page-parameter", "builder-changes-actions")

    assert _failed(*args, ["update_action"], set_parameters("'latest'")) == set()
    assert _failed(*args, ["update_action"], set_parameters("'latest'", "'7'")) == {
        "id is unchanged"
    }
    assert _failed(*args, [], set_parameters("'first'")) == {
        "called update_action",
        "slug is 'latest'",
    }


_OUR_DATASETS = {
    "kuma-core",
    "kuma-database",
    "kuma-docs",
    "kuma-builder",
    "kuma-automation",
    "kuma-prod-replay",
}

EXPECTED_CASE_IDS = {
    "kuma-core": [
        "core/audit-log-what-changed",
        "core/audit-log-who-deleted",
        "core/creates-application",
        "core/creates-automation",
        "core/creates-dashboard",
        "core/creates-database",
        "core/creates-several-applications",
        "core/lists-databases",
        "core/renames-automation",
        "core/search-finds-row",
        "core/search-finds-table",
    ],
    "kuma-database": [
        "database/adds-row-comment",
        "database/colours-rows",
        "database/creates-database-from-description",
        "database/creates-related-tables",
        "database/creates-related-tables-with-sample-rows",
        "database/creates-rows-with-all-field-types",
        "database/creates-simple-table",
        "database/creates-table-with-select-fields",
        "database/creates-view-calendar",
        "database/creates-view-filter-boolean-equal",
        "database/creates-view-filter-date-after",
        "database/creates-view-filter-multiple-select-has",
        "database/creates-view-filter-number-greater-than",
        "database/creates-view-filter-single-select-is-any-of",
        "database/creates-view-filter-text-contains",
        "database/creates-view-form",
        "database/creates-view-gallery",
        "database/creates-view-grid",
        "database/creates-view-kanban",
        "database/creates-view-timeline",
        "database/deletes-field",
        "database/reads-row-comments",
        "database/renames-field",
        "database/sorts-view",
        "database/updates-select-options",
    ],
    "kuma-docs": [
        "docs/address-autocomplete-field",
        "docs/airtable-import",
        "docs/api-401-error",
        "docs/api-docs-overview",
        "docs/api-filter-rows",
        "docs/api-pagination",
        "docs/auto-number-field",
        "docs/auto-save",
        "docs/calendar-with-filter",
        "docs/cancel-free-trial",
        "docs/checkbox-email-automation",
        "docs/concat-upper-formula",
        "docs/conditional-formatting",
        "docs/conditional-options-plan-question",
        "docs/count-linked-rows",
        "docs/create-api-token",
        "docs/create-dashboard",
        "docs/create-database",
        "docs/create-view",
        "docs/custom-css-core-ui",
        "docs/dark-mode",
        "docs/data-recovery",
        "docs/date-diff-formula",
        "docs/delete-multiple-rows",
        "docs/delete-row",
        "docs/docker-upgrade",
        "docs/duplicate-row",
        "docs/embed-public-view",
        "docs/entra-sso",
        "docs/export-database",
        "docs/field-permissions",
        "docs/folders-in-database",
        "docs/form-edit-existing-row",
        "docs/form-tabs-multistep",
        "docs/formula-previous-row",
        "docs/formula-today",
        "docs/free-plan-row-limit",
        "docs/gallery-image-size",
        "docs/group-by-view",
        "docs/hide-fields",
        "docs/import-csv",
        "docs/import-excel",
        "docs/invite-users",
        "docs/kanban-view",
        "docs/link-two-tables",
        "docs/mcp-server",
        "docs/ocr-scan",
        "docs/own-rows-only-permissions",
        "docs/per-cell-color",
        "docs/phone-number-field",
        "docs/plan-for-field-level-permissions",
        "docs/raw-sql-cloud-plan",
        "docs/recover-deleted-table",
        "docs/rename-table",
        "docs/rename-workspace",
        "docs/row-height",
        "docs/row-history-retention",
        "docs/share-view-read-only",
        "docs/sum-column",
        "docs/sync-column-widths",
        "docs/templates",
        "docs/upload-file",
        "docs/vlookup-to-link-row",
        "docs/webhooks-availability",
    ],
    "kuma-builder": [
        "builder/adds-edit-button-column",
        "builder/asks-once-when-goal-unclear",
        "builder/asks-when-implied-table-missing",
        "builder/asks-when-named-table-missing",
        "builder/back-button-on-page-not-header",
        "builder/builds-demo-page-without-asking",
        "builder/builds-example-app-without-asking",
        "builder/changes-detail-path-keeps-param-type",
        "builder/changes-notification-title",
        "builder/changes-open-page-parameter",
        "builder/changes-theme",
        "builder/creates-app-when-table-exists",
        "builder/creates-app-with-theme",
        "builder/creates-contact-form",
        "builder/creates-data-source-with-repeat",
        "builder/creates-header-with-menu",
        "builder/creates-landing-page",
        "builder/creates-new-page-not-modifies-existing",
        "builder/creates-product-detail-page",
        "builder/creates-table-with-edit-button",
        "builder/edits-table-columns",
        "builder/filtered-data-source-via-view",
        "builder/keeps-link-column-settings",
        "builder/lists-pages",
        "builder/menu-adds-link-keeps-button",
        "builder/menu-adds-pages-one-by-one",
        "builder/menu-button-opens-page",
        "builder/menu-removes-dropdown",
        "builder/menu-removes-sub-link",
        "builder/menu-renames-button",
        "builder/menu-reorders-items",
        "builder/moves-element-out-of-column",
        "builder/moves-table-column",
        "builder/page-specific-nav-on-page",
        "builder/sets-detail-row-from-url",
        "builder/setup-user-source-existing-table",
        "builder/setup-user-source-new-table",
    ],
    "kuma-automation": [
        "automation/adds-slack-to-router-branch",
        "automation/changes-router-condition",
        "automation/creates-email-notification-workflow",
        "automation/creates-router-workflow",
        "automation/creates-row-with-field-values",
        "automation/creates-update-row-workflow",
        "automation/creates-weekly-slack-reminder",
        "automation/creates-workflow",
        "automation/deletes-node",
        "automation/edits-email-subject",
        "automation/lists-workflows",
    ],
    "kuma-prod-replay": [
        "prod-replay/fake-rows-into-typed-fields",
        "prod-replay/form-for-table-with-formula-field",
        "prod-replay/impossible-formula-request",
        "prod-replay/iso-week-number-formula",
        "prod-replay/orders-linked-to-number-primary",
        "prod-replay/page-at-taken-path",
        "prod-replay/page-inspection-existing-elements",
        "prod-replay/project-tracker-onboarding",
        "prod-replay/signed-amount-formula",
    ],
}

# builder/creates-app-with-theme bypassed mode derivation in the legacy test
# (bare workspace UIContext, direct agent.run_sync call) and stayed at the
# AssistantDeps default of DATABASE; every other builder case derived
# APPLICATION from its application-slot UIContext. All automation cases never
# set deps.mode, so they ran (and still run) in DATABASE mode too.
# Prod-replay derived mode from the UI context: the builder replays run in
# APPLICATION, every other replay in DATABASE.
EXPECTED_MODES = {
    **{
        case_id: AgentMode.APPLICATION
        for case_id in EXPECTED_CASE_IDS["kuma-builder"]
        if case_id != "builder/creates-app-with-theme"
    },
    "builder/creates-app-with-theme": AgentMode.DATABASE,
    **{case_id: AgentMode.DATABASE for case_id in EXPECTED_CASE_IDS["kuma-automation"]},
    **{
        case_id: AgentMode.DATABASE for case_id in EXPECTED_CASE_IDS["kuma-prod-replay"]
    },
    "prod-replay/page-inspection-existing-elements": AgentMode.APPLICATION,
    "prod-replay/page-at-taken-path": AgentMode.APPLICATION,
}


def _our_cases():
    return [c for c in all_cases() if c.dataset in _OUR_DATASETS]


class TestDatasetCounts:
    def test_case_counts_per_dataset(self):
        grouped = cases_by_dataset()

        assert len(grouped["kuma-core"]) == 11
        assert len(grouped["kuma-database"]) == 25
        assert len(grouped["kuma-docs"]) == 64
        assert len(grouped["kuma-builder"]) == 37
        assert len(grouped["kuma-automation"]) == 11
        assert len(grouped["kuma-prod-replay"]) == 9

    def test_case_ids_match_inventory(self):
        grouped = cases_by_dataset()

        for dataset, expected_ids in EXPECTED_CASE_IDS.items():
            assert [c.id for c in grouped[dataset]] == expected_ids

    def test_all_case_ids_unique(self):
        ids = [c.id for c in _our_cases()]

        assert len(ids) == len(set(ids))


class TestEveryCaseScenarioResolves:
    @pytest.mark.parametrize("case", _our_cases(), ids=lambda c: c.id)
    def test_scenario_is_registered(self, case):
        get_scenario(case.scenario)


class TestDocsCasesFlagKnowledgeBase:
    def test_docs_cases_require_knowledge_base(self):
        docs_cases = cases_by_dataset()["kuma-docs"]

        assert all(c.requires_knowledge_base for c in docs_cases)

    def test_non_docs_cases_do_not_require_knowledge_base(self):
        for dataset in ("kuma-core", "kuma-database"):
            assert all(
                not c.requires_knowledge_base for c in cases_by_dataset()[dataset]
            )


class TestAgentModes:
    """Mode is scenario configuration, not derived — pin it per case id."""

    @pytest.mark.parametrize(
        "case",
        [
            c
            for c in _our_cases()
            if c.dataset in ("kuma-builder", "kuma-automation", "kuma-prod-replay")
        ],
        ids=lambda c: c.id,
    )
    def test_mode_matches_inventory(self, case):
        assert case.mode == EXPECTED_MODES[case.id]


@pytest.mark.django_db
class TestBuilderPreStateSnapshots:
    """The two cases that need a pre-run DB snapshot must populate pre_state."""

    def test_changes_theme_snapshots_initial_color(self):
        scenario = get_scenario("builder-changes-theme")(make_fixtures())

        assert "initial_color" in scenario.pre_state

    def test_creates_new_page_snapshots_home_page_state(self):
        scenario = get_scenario("builder-creates-new-page-not-modifies-existing")(
            make_fixtures()
        )

        assert scenario.pre_state["home_element_count"] == 2
        assert scenario.pre_state["home_page_id"] == scenario.refs["home_page"].id


@pytest.mark.django_db
class TestScenarioSmoke:
    """Instantiates every scenario referenced by these datasets, LLM-free."""

    @pytest.mark.parametrize(
        "scenario_name", sorted({c.scenario for c in _our_cases()})
    )
    def test_scenario_builds_without_error(self, scenario_name):
        scenario = get_scenario(scenario_name)(make_fixtures())

        assert scenario.user.pk is not None
        assert scenario.workspace.pk is not None
        if scenario.ui_context is not None:
            json.loads(scenario.ui_context)
