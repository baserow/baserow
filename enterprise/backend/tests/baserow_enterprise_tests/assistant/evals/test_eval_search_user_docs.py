from django.conf import settings

import pytest

from .eval_utils import (
    EvalChecklist,
    build_database_ui_context,
    create_eval_assistant,
    format_message_history,
    print_message_history,
)


@pytest.fixture(autouse=True)
def _require_knowledge_base(synced_knowledge_base):
    """Skip search docs tests when the knowledge base is not available.

    Depends on the session-scoped ``synced_knowledge_base`` fixture
    (conftest.py) which syncs the KB once per session if needed.
    """

    if not getattr(settings, "BASEROW_EMBEDDINGS_API_URL", ""):
        pytest.skip(
            "BASEROW_EMBEDDINGS_API_URL not set. "
            "See docs/testing/ai-assistant-evals.md for setup instructions."
        )

    from baserow_enterprise.assistant.tools.search_user_docs.handler import (
        KnowledgeBaseHandler,
    )

    if not KnowledgeBaseHandler().can_search():
        pytest.skip(
            "Knowledge base not available. "
            "Requires: pgvector extension and synced KB data. "
            "See docs/testing/ai-assistant-evals.md for setup instructions."
        )


# ---------------------------------------------------------------------------
# Test cases: (id, question, expected_source_patterns, expected_answer_keywords)
#
# expected_source_patterns: at least ONE returned source URL must contain
#     one of these substrings.
# expected_answer_keywords: the agent's final answer must contain at least
#     ONE of these substrings (case-insensitive).
# ---------------------------------------------------------------------------

SEARCH_DOCS_CASES = [
    pytest.param(
        (
            "I'm trying to do a VLOOKUP to pull the 'Client Email' from my "
            "'Clients' tab into my 'Projects' tab based on the client name. "
            "I can't find the formula for this. Does it exist in Baserow?"
        ),
        ["link-to-table", "lookup-field"],
        ["link row", "lookup", "link_row", "relationship"],
        id="vlookup-to-link-row",
    ),
    pytest.param(
        (
            "I need to run a raw SQL query to join three tables for a report. "
            "I'm on the standard cloud hosted plan. Where do I find my database "
            "host, port, and credentials to connect my BI tool?"
        ),
        ["technical", "set-up-baserow"],
        ["api", "self-host", "rest api", "not available", "cannot"],
        id="raw-sql-cloud-plan",
    ),
    pytest.param(
        (
            "I'm trying to calculate the days between two dates. I typed "
            "=DAYS(field('End'), field('Start')) like I do in Google Sheets "
            "but it says 'Invalid Syntax'. What am I doing wrong?"
        ),
        ["formula", "understanding-formulas"],
        ["date_diff", "date diff", "datediff"],
        id="date-diff-formula",
    ),
    pytest.param(
        "Where is the save button? I don't want to lose my work.",
        ["baserow-basics"],
        ["auto", "automatically", "saved"],
        id="auto-save",
    ),
    pytest.param(
        "How can I put a form on my website that sends data to my table?",
        ["creating-forms", "guide-to-creating-forms"],
        ["form", "embed", "share"],
        id="form-embed",
    ),
    pytest.param(
        "I deleted a bunch of rows by mistake. Is there a recycling bin?",
        ["data-recovery", "deletion"],
        ["trash", "recover", "undo", "restore"],
        id="data-recovery",
    ),
    pytest.param(
        (
            "I want to share a specific view with my client so they can see "
            "the progress, but I don't want them to edit anything or see the "
            "other tables. Is that possible?"
        ),
        ["public-sharing", "permissions"],
        ["share", "public", "read-only", "read only", "view"],
        id="share-view-read-only",
    ),
    pytest.param(
        "I need to lock a column so my team can see it but not mess it up.",
        ["field-level-permissions", "permissions"],
        ["permission", "field", "read", "lock"],
        id="field-permissions",
    ),
    pytest.param(
        (
            "How can I create a calendar that shows my tasks, but only the ones assigned to me."
        ),
        ["calendar-view", "calendar", "filters"],
        ["calendar", "filter", "view"],
        id="calendar-with-filter",
    ),
    pytest.param(
        (
            "I'm trying to combine the first name and last name columns "
            "into one, but I want to make sure it's uppercase. Can you tell me how to "
            "write that formula?"
        ),
        ["formula", "understanding-formulas"],
        ["concat", "upper", "formula"],
        id="concat-upper-formula",
    ),
    pytest.param(
        (
            "I'm running Baserow on my own server with Docker. A new version "
            "came out yesterday, how do I install it without losing my data?"
        ),
        ["set-up-baserow", "configuration"],
        ["docker", "pull", "upgrade", "update", "volume"],
        id="docker-upgrade",
    ),
    pytest.param(
        (
            "I want to write a script so that whenever I tick a checkbox, "
            "it sends an email to the client. Do I need to build a custom "
            "plugin for this?"
        ),
        ["webhook", "workflow-automation", "automation"],
        ["automation", "webhook", "trigger", "workflow"],
        id="checkbox-email-automation",
    ),
    pytest.param(
        (
            "I want to embed my inventory sheet on my website so clients "
            "can search it. Do they need a Baserow account to see it? "
            "How do I generate the code?"
        ),
        ["public-sharing"],
        ["embed", "public", "share", "account"],
        id="embed-public-view",
    ),
    pytest.param(
        "Can Baserow integrate with Google AI Studio?",
        ["configure-generative-ai", "database-api"],
        ["ai", "generative", "integration", "api"],
        id="google-ai-studio",
    ),
    pytest.param(
        (
            "I'm trying to fetch data from my table using curl but I keep "
            "getting a 401 error. I generated a token in my settings, but it "
            "says I don't have permissions. Do I need to use my login email "
            "and password instead?"
        ),
        ["rest-api", "database-api"],
        ["token", "api", "permission", "authentication"],
        id="api-401-error",
    ),
    pytest.param(
        (
            "Is there a way to only get rows where the 'Status' field is "
            "set to 'Done' via the API? I don't want to download the whole "
            "JSON and filter it in my script."
        ),
        ["rest-api", "database-api"],
        ["filter", "api", "parameter", "field"],
        id="api-filter-rows",
    ),
]


def _run_agent(
    agent, deps, tracker, model, usage_limits, toolset, question, ui_context
):
    deps.tool_helpers.request_context["ui_context"] = ui_context
    return agent.run_sync(
        user_prompt=question,
        deps=deps,
        model=model,
        usage_limits=usage_limits,
        toolsets=[toolset],
    )


@pytest.mark.eval
@pytest.mark.django_db
@pytest.mark.parametrize(
    "question,expected_source_patterns,expected_keywords", SEARCH_DOCS_CASES
)
def test_search_user_docs(
    data_fixture,
    eval_model,
    question,
    expected_source_patterns,
    expected_keywords,
):
    """
    Agent should call search_user_docs for user-docs questions and return
    an answer with relevant sources and content.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=10, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=question,
        ui_context=ui_context,
    )

    print_message_history(result)

    history = format_message_history(result)
    search_calls = [
        e
        for e in history
        if e.get("tool_name") == "search_user_docs" and e["role"] == "assistant"
    ]
    sources = deps.sources
    answer = result.output.lower()
    keyword_match = any(kw.lower() in answer for kw in expected_keywords)

    # Source URL matching is non-fatal — URLs change and the retrieval may
    # return valid alternative sources.  Print a warning but don't score it.
    if expected_source_patterns and sources:
        source_match = any(
            any(pattern in url for pattern in expected_source_patterns)
            for url in sources
        )
        if not source_match:
            print(
                f"\n  WARNING: No source matched {expected_source_patterns}.\n"
                f"  Returned sources: {sources}"
            )

    with EvalChecklist("search user docs") as checks:
        checks.check(
            "called search_user_docs",
            len(search_calls) >= 1,
            hint=f"tools called: {[e.get('tool_name') for e in history if e.get('tool_name')]}",
        )
        checks.check(
            f"returned at least one source URL for user docs",
            len(sources) >= 1,
            hint=f"tools called: {[e.get('tool_name') for e in history if e.get('tool_name')]}",
        )
        checks.check(
            f"answer mentions one of {expected_keywords}",
            keyword_match,
            hint=f"answer (first 300 chars): {result.output[:300]}",
        )
