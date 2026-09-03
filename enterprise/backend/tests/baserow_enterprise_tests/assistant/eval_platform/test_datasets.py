"""Structure-level tests for the kuma-core/database/docs eval datasets.

No LLM calls here: these only check that registration produced the right
shape (case ids, counts, scenario wiring). ``TestScenarioSmoke`` is the one
class that touches the database, to build every scenario once.
"""

import json

import pytest

from baserow_enterprise.assistant.deps import AgentMode
from baserow_enterprise.assistant.evals.registry import (
    all_cases,
    cases_by_dataset,
    get_scenario,
    load_all,
)
from baserow_enterprise.assistant.evals.scenarios import make_fixtures

load_all()

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
        "core/creates-automation",
        "core/creates-database",
        "core/lists-databases",
    ],
    "kuma-database": [
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
        "database/renames-field",
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
        "builder/asks-once-when-goal-unclear",
        "builder/asks-when-named-table-missing",
        "builder/back-button-on-page-not-header",
        "builder/builds-demo-page-without-asking",
        "builder/builds-example-app-without-asking",
        "builder/builds-projects-app-proactively",
        "builder/changes-theme",
        "builder/creates-app-when-table-exists",
        "builder/creates-app-with-theme",
        "builder/creates-contact-form",
        "builder/creates-data-source-with-repeat",
        "builder/creates-header-with-menu",
        "builder/creates-landing-page",
        "builder/creates-new-page-not-modifies-existing",
        "builder/creates-table-with-edit-button",
        "builder/filtered-data-source-via-view",
        "builder/lists-pages",
        "builder/page-specific-nav-on-page",
        "builder/setup-user-source-existing-table",
        "builder/setup-user-source-new-table",
    ],
    "kuma-automation": [
        "automation/creates-email-notification-workflow",
        "automation/creates-router-workflow",
        "automation/creates-row-with-field-values",
        "automation/creates-update-row-workflow",
        "automation/creates-weekly-slack-reminder",
        "automation/creates-workflow",
        "automation/lists-workflows",
    ],
    "kuma-prod-replay": [
        "prod-replay/fake-rows-into-typed-fields",
        "prod-replay/form-for-table-with-formula-field",
        "prod-replay/impossible-formula-request",
        "prod-replay/iso-week-number-formula",
        "prod-replay/page-inspection-existing-elements",
        "prod-replay/project-tracker-onboarding",
        "prod-replay/signed-stock-effect-formula",
    ],
}

# builder/creates-app-with-theme bypassed mode derivation in the legacy test
# (bare workspace UIContext, direct agent.run_sync call) and stayed at the
# AssistantDeps default of DATABASE; every other builder case derived
# APPLICATION from its application-slot UIContext. All automation cases never
# set deps.mode, so they ran (and still run) in DATABASE mode too.
# Prod-replay derived mode from the UI context: builder page inspection ran in
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
}


def _our_cases():
    return [c for c in all_cases() if c.dataset in _OUR_DATASETS]


class TestDatasetCounts:
    def test_case_counts_per_dataset(self):
        grouped = cases_by_dataset()

        assert len(grouped["kuma-core"]) == 3
        assert len(grouped["kuma-database"]) == 21
        assert len(grouped["kuma-docs"]) == 64
        assert len(grouped["kuma-builder"]) == 20
        assert len(grouped["kuma-automation"]) == 7
        assert len(grouped["kuma-prod-replay"]) == 7

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
