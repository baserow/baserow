"""Structure-level tests for the kuma-core/database/docs eval datasets.

No LLM calls here: these only check that registration produced the right
shape (case ids, counts, scenario wiring). ``TestScenarioSmoke`` is the one
class that touches the database, to build every scenario once.
"""

import json

import pytest

from baserow_enterprise.assistant.evals.registry import (
    all_cases,
    cases_by_dataset,
    get_scenario,
    load_all,
)
from baserow_enterprise.assistant.evals.scenarios import make_fixtures

load_all()

_OUR_DATASETS = {"kuma-core", "kuma-database", "kuma-docs"}

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
        "docs/api-401-error",
        "docs/api-filter-rows",
        "docs/auto-save",
        "docs/calendar-with-filter",
        "docs/checkbox-email-automation",
        "docs/concat-upper-formula",
        "docs/conditional-options-plan-question",
        "docs/data-recovery",
        "docs/date-diff-formula",
        "docs/docker-upgrade",
        "docs/embed-public-view",
        "docs/field-permissions",
        "docs/form-embed",
        "docs/google-ai-studio",
        "docs/plan-for-field-level-permissions",
        "docs/raw-sql-cloud-plan",
        "docs/share-view-read-only",
        "docs/vlookup-to-link-row",
    ],
}


def _our_cases():
    return [c for c in all_cases() if c.dataset in _OUR_DATASETS]


class TestDatasetCounts:
    def test_case_counts_per_dataset(self):
        grouped = cases_by_dataset()

        assert len(grouped["kuma-core"]) == 3
        assert len(grouped["kuma-database"]) == 21
        assert len(grouped["kuma-docs"]) == 18

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
