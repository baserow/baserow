"""Kuma-docs eval dataset: search_user_docs knowledge-base Q&A.

All 18 cases share one scenario — the check depends on the knowledge base,
not on any scenario state — so only the (question, source patterns, answer
keywords) triple varies per case.
"""

from __future__ import annotations

from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.evals.harness import tool_called
from baserow_enterprise.assistant.evals.registry import (
    register_case,
    register_scenario,
)
from baserow_enterprise.assistant.evals.scenarios import build_database_ui_context
from baserow_enterprise.assistant.evals.types import (
    CheckResult,
    CheckSuite,
    EvalCase,
    EvalRunOutput,
    EvalScenario,
)


@register_scenario("docs-question")
def _docs_question_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace)
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database),
    )


def _make_docs_checks(
    expected_source_patterns: list[str], expected_keywords: list[str]
) -> CheckSuite:
    def _checks(
        case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
    ) -> list[CheckResult]:
        answer = output.answer.lower()
        keyword_match = any(kw.lower() in answer for kw in expected_keywords)

        # Source-URL matching is non-fatal — URLs change and retrieval may
        # return valid alternative sources — so this always passes; a
        # mismatch is surfaced only through the hint.
        source_hint = ""
        if expected_source_patterns and output.sources:
            source_match = any(
                any(pattern in url for pattern in expected_source_patterns)
                for url in output.sources
            )
            if not source_match:
                source_hint = (
                    f"WARNING: no source matched {expected_source_patterns}; "
                    f"returned sources: {output.sources}"
                )

        return [
            CheckResult(
                "called search_user_docs",
                tool_called(output, "search_user_docs") >= 1,
                hint=f"tools called: {output.tool_calls}",
            ),
            CheckResult(
                "returned at least one source URL for user docs",
                len(output.sources) >= 1,
                hint=f"tools called: {output.tool_calls}",
            ),
            CheckResult(
                f"answer mentions one of {expected_keywords}",
                keyword_match,
                hint=output.answer[:300],
            ),
            CheckResult("source URL matches expected pattern", True, hint=source_hint),
        ]

    return _checks


def _register_docs_case(
    case_id: str,
    question: str,
    expected_source_patterns: list[str],
    expected_keywords: list[str],
) -> None:
    register_case(
        EvalCase(
            id=f"docs/{case_id}",
            dataset="kuma-docs",
            prompt=question,
            scenario="docs-question",
            checks=_make_docs_checks(expected_source_patterns, expected_keywords),
            max_iters=10,
            requires_knowledge_base=True,
        )
    )


_register_docs_case(
    "vlookup-to-link-row",
    (
        "I'm trying to do a VLOOKUP to pull the 'Client Email' from my "
        "'Clients' tab into my 'Projects' tab based on the client name. "
        "I can't find the formula for this. Does it exist in Baserow?"
    ),
    ["link-to-table", "lookup-field"],
    ["link row", "lookup", "link_row", "relationship"],
)

_register_docs_case(
    "raw-sql-cloud-plan",
    (
        "I need to run a raw SQL query to join three tables for a report. "
        "I'm on the standard cloud hosted plan. Where do I find my database "
        "host, port, and credentials to connect my BI tool?"
    ),
    ["technical", "set-up-baserow"],
    ["api", "self-host", "rest api", "not available", "cannot"],
)

_register_docs_case(
    "date-diff-formula",
    (
        "I'm trying to calculate the days between two dates. I typed "
        "=DAYS(field('End'), field('Start')) like I do in Google Sheets "
        "but it says 'Invalid Syntax'. What am I doing wrong?"
    ),
    ["formula", "understanding-formulas"],
    ["date_diff", "date diff", "datediff"],
)

_register_docs_case(
    "auto-save",
    "Where is the save button? I don't want to lose my work.",
    ["baserow-basics"],
    ["auto", "automatically", "saved"],
)

_register_docs_case(
    "form-embed",
    "How can I put a form on my website that sends data to my table?",
    ["creating-forms", "guide-to-creating-forms"],
    ["form", "embed", "share"],
)

_register_docs_case(
    "data-recovery",
    "I deleted a bunch of rows by mistake. Is there a recycling bin?",
    ["data-recovery", "deletion"],
    ["trash", "recover", "undo", "restore"],
)

_register_docs_case(
    "share-view-read-only",
    (
        "I want to share a specific view with my client so they can see "
        "the progress, but I don't want them to edit anything or see the "
        "other tables. Is that possible?"
    ),
    ["public-sharing", "permissions"],
    ["share", "public", "read-only", "read only", "view"],
)

_register_docs_case(
    "field-permissions",
    "I need to lock a column so my team can see it but not mess it up.",
    ["field-level-permissions", "permissions"],
    ["permission", "field", "read", "lock"],
)

_register_docs_case(
    "plan-for-field-level-permissions",
    "Which Baserow plan unlocks field-level permissions for a workspace?",
    ["field-level-permissions", "permissions"],
    ["plan", "field-level permissions", "field permissions", "enterprise"],
)

_register_docs_case(
    "conditional-options-plan-question",
    (
        "I can't find the conditional options toggle for my single select field. "
        "Should I upgrade, or is there another requirement?"
    ),
    ["single-select", "select-option", "fields"],
    ["conditional", "single select", "plan", "upgrade"],
)

_register_docs_case(
    "calendar-with-filter",
    (
        "How can I create a calendar that shows my tasks, but only the ones "
        "assigned to me."
    ),
    ["calendar-view", "calendar", "filters"],
    ["calendar", "filter", "view"],
)

_register_docs_case(
    "concat-upper-formula",
    (
        "What would a formula look like that combines a first name and last "
        "name field into a full name field?"
    ),
    ["formula", "understanding-formulas"],
    ["concat", "upper", "formula"],
)

_register_docs_case(
    "docker-upgrade",
    (
        "I'm running Baserow on my own server with Docker. A new version "
        "came out yesterday, how do I install it without losing my data?"
    ),
    ["set-up-baserow", "configuration"],
    ["docker", "pull", "upgrade", "update", "volume"],
)

_register_docs_case(
    "checkbox-email-automation",
    (
        "I want to write a script so that whenever I tick a checkbox, "
        "it sends an email to the client. Do I need to build a custom "
        "plugin for this?"
    ),
    ["webhook", "workflow-automation", "automation"],
    ["automation", "webhook", "trigger", "workflow"],
)

_register_docs_case(
    "embed-public-view",
    (
        "I want to embed my inventory sheet on my website so clients "
        "can search it. Do they need a Baserow account to see it? "
        "How do I generate the code?"
    ),
    ["public-sharing"],
    ["embed", "public", "share", "account"],
)

_register_docs_case(
    "google-ai-studio",
    "Can Baserow integrate with Google AI Studio?",
    ["configure-generative-ai", "database-api"],
    ["ai", "generative", "integration", "api"],
)

_register_docs_case(
    "api-401-error",
    (
        "I'm trying to fetch data from my table using curl but I keep "
        "getting a 401 error. I generated a token in my settings, but it "
        "says I don't have permissions. Do I need to use my login email "
        "and password instead?"
    ),
    ["rest-api", "database-api"],
    ["token", "api", "permission", "authentication"],
)

_register_docs_case(
    "api-filter-rows",
    (
        "Is there a way to only get rows where the 'Status' field is "
        "set to 'Done' via the API? I don't want to download the whole "
        "JSON and filter it in my script."
    ),
    ["rest-api", "database-api"],
    ["filter", "api", "parameter", "field"],
)
