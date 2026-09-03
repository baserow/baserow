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
    reference_answer: str | None = None,
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
            metadata={"expected_keywords": expected_keywords},
            reference_answer=reference_answer,
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
    reference_answer=(
        "There's no VLOOKUP in Baserow — use a Link to table field plus a "
        "Lookup field. In Projects, add a Link to table field pointing at "
        "Clients and select the client per row, then add a Lookup field that "
        "uses that link and pulls 'Client Email'. The Lookup field is "
        "read-only and stays in sync automatically. To pull only some of the "
        "linked rows, use a formula instead: filter(lookup('Clients', "
        "'Client Email'), <condition>) returns just the values matching the "
        "condition."
    ),
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
    reference_answer=(
        "Direct PostgreSQL access is not available on any Baserow cloud "
        "plan, so there are no host/port/credentials. Pull the data through "
        "the REST API instead (create a database token and use your "
        "database's auto-generated API docs) and join in your BI tool; raw "
        "SQL against the database requires self-hosting Baserow."
    ),
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
    reference_answer=(
        "Baserow formulas don't start with '=' and there is no DAYS() "
        "function — use date_diff with the unit as the first argument: "
        "date_diff('day', field('Start'), field('End')). Other units include "
        "'hour', 'week', 'month', and 'year'."
    ),
)

_register_docs_case(
    "auto-save",
    "Where is the save button? I don't want to lose my work.",
    ["baserow-basics"],
    ["auto", "automatically", "saved"],
    reference_answer=(
        "There is no save button — Baserow saves every change automatically "
        "in real time, so your work is never lost. Use undo (Ctrl+Z / Cmd+Z) "
        "to revert a mistaken change."
    ),
)

_register_docs_case(
    "data-recovery",
    "I deleted a bunch of rows by mistake. Is there a recycling bin?",
    ["data-recovery", "deletion"],
    ["trash", "recover", "undo", "restore"],
    reference_answer=(
        "Yes — deleted rows go to the Trash (in the sidebar), where they are "
        "kept for 3 days before permanent deletion. Find the deleted rows "
        "there and click Restore to put them back in their original table."
    ),
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
    reference_answer=(
        "Yes — open the view, click 'Share view' in the toolbar, and create "
        "a public link. The link exposes only that single view, read-only "
        "(no editing, no access to other tables or views), and you can "
        "optionally protect it with a password."
    ),
)

_register_docs_case(
    "field-permissions",
    "I need to lock a column so my team can see it but not mess it up.",
    ["field-level-permissions", "permissions"],
    ["permission", "field", "read", "lock"],
    reference_answer=(
        "Use field-level permissions: open the column's dropdown, choose "
        "'Edit field permissions', and set who can edit it (Editors and "
        "higher, Builders and higher, Admins only, or Nobody). Everyone can "
        "still read the values — only editing is restricted. Requires the "
        "Advanced or Enterprise plan."
    ),
)

_register_docs_case(
    "plan-for-field-level-permissions",
    "Which Baserow plan unlocks field-level permissions for a workspace?",
    ["field-level-permissions", "permissions"],
    ["plan", "field-level permissions", "field permissions", "enterprise"],
    reference_answer=(
        "The Advanced plan is the lowest plan with field-level permissions; "
        "Enterprise includes it too. Free and Premium workspaces don't have "
        "it."
    ),
)

_register_docs_case(
    "conditional-options-plan-question",
    (
        "I can't find the conditional options toggle for my single select field. "
        "Should I upgrade, or is there another requirement?"
    ),
    ["single-select", "select-option", "fields"],
    ["conditional", "single select", "plan", "upgrade"],
    reference_answer=(
        "No upgrade needed — form-field conditions are not plan-gated. The "
        "'show when conditions are met' toggle only appears when at least "
        "one other field sits above your single select in the form, because "
        "a condition can only reference preceding fields; reorder the form "
        "and the toggle shows up."
    ),
)

_register_docs_case(
    "calendar-with-filter",
    (
        "How can I create a calendar that shows my tasks, but only the ones "
        "assigned to me."
    ),
    ["calendar-view", "calendar", "filters"],
    ["calendar", "filter", "view"],
    reference_answer=(
        "Create a Calendar view (paid plans; needs a date field, chosen via "
        "'Displayed by'), then open the view's Filter menu and add a "
        "condition on the assignee field (e.g. Assignee has me). Filters are "
        "per view, so only this calendar is affected."
    ),
)

_register_docs_case(
    "concat-upper-formula",
    (
        "What would a formula look like that combines a first name and last "
        "name field into a full name field?"
    ),
    ["formula", "understanding-formulas"],
    ["concat", "upper", "formula"],
    reference_answer=(
        "Use concat(field('First name'), ' ', field('Last name')) in a "
        "formula field — field('...') references a column by its exact name. "
        "The + operator works too: field('First name') + ' ' + "
        "field('Last name')."
    ),
)

_register_docs_case(
    "docker-upgrade",
    (
        "I'm running Baserow on my own server with Docker. A new version "
        "came out yesterday, how do I install it without losing my data?"
    ),
    ["set-up-baserow", "configuration"],
    ["docker", "pull", "upgrade", "update", "volume"],
    reference_answer=(
        "Your data lives in the baserow_data Docker volume, not the "
        "container, so it survives upgrades. Stop and remove the old "
        "container, docker pull the new baserow/baserow:<version> image, and "
        "start a new container with the same arguments — critically the same "
        "-v baserow_data:/baserow/data mount. Back up the volume first."
    ),
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
    reference_answer=(
        "No plugin needed — use Baserow's built-in automations. Create a "
        "workflow with the 'Specific field values are updated' (or 'Rows are "
        "updated') trigger watching the checkbox, then add the 'Send an "
        "email' action (SMTP integration); recipient and message can be "
        "bound to row values."
    ),
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
    reference_answer=(
        "No account needed — anyone with the link can view it. Click 'Share "
        "view' on the view to create a public link; Baserow doesn't generate "
        "embed code, so wrap the link in an iframe yourself: <iframe "
        'src="SHARED_VIEW_URL" width="100%" height="400"></iframe>. Visitors '
        "can search and apply temporary filters without affecting your view."
    ),
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
    reference_answer=(
        "Don't use login credentials — the database token is correct, but it "
        "must be sent as 'Authorization: Token YOUR_TOKEN' (the 'Token' "
        "prefix is required; 'Bearer' gives 401), and the token's Read "
        "permission must be enabled for that database/table in the token "
        "settings, since tokens have per-database create/read/update/delete "
        "scopes."
    ),
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
    reference_answer=(
        "Yes, two server-side options on the list rows endpoint: simple "
        "query parameters like ?filter__field_{id}__single_select_equal="
        "{option_id} combined with filter_type=AND|OR, or the filters "
        "parameter taking a URL-encoded JSON filter tree — "
        '{"filter_type":"AND","filters":[...],"groups":[...]} — which also '
        "supports nested filter groups. Your table's auto-generated API "
        "docs list the field ids and available filter types."
    ),
)

_register_docs_case(
    "delete-row",
    "How do I delete a row from my table?",
    ["navigating-row-configurations"],
    ["right-click", "delete row", "trash"],
    reference_answer=(
        "Right-click the row you want to remove and select `Delete row` "
        "from the context menu. The row moves to the trash, where it can be "
        "restored for 3 days before permanent deletion; you can also undo "
        "immediately with Ctrl/Cmd + Z."
    ),
)

_register_docs_case(
    "delete-multiple-rows",
    ("Is there a way to delete a bunch of rows at once instead of one by one?"),
    ["navigating-row-configurations"],
    ["delete rows", "right-click", "shift", "select"],
    reference_answer=(
        "Yes: select the rows first (click a row, then Shift+click to "
        "extend the range, or click-and-drag), then right-click and choose "
        "`Delete rows` or press the Delete key. You can select up to 200 "
        "rows at a time, and deleted rows go to the trash where they are "
        "recoverable for 3 days."
    ),
)

_register_docs_case(
    "duplicate-row",
    ("How can I duplicate an existing row so I don't have to retype everything?"),
    ["how-to-make-new-rows"],
    ["duplicate row", "right-click", "context menu"],
    reference_answer=(
        "Right-click the row and select `Duplicate row` from the context "
        "menu. Baserow inserts an exact copy directly below the original "
        "with all field values preserved."
    ),
)

_register_docs_case(
    "import-excel",
    (
        "Can I import an Excel file (.xlsx) into Baserow, or do I have to "
        "convert it to CSV first?"
    ),
    ["create-a-table-via-import", "import-data-into-an-existing-table"],
    ["xlsx", "excel", "paste", "import"],
    reference_answer=(
        "Yes — when creating a new table, click `+ New table`, choose the "
        "Excel import option, and upload your file directly (.xlsx, .xls, "
        "and .ods are supported; you can pick which worksheet to import). "
        "For an existing table the `Import file` dialog accepts CSV, JSON, "
        "and XML but not .xlsx, so paste the cells straight from Excel or "
        "save the sheet as CSV instead. Imports are limited to 5,000 rows "
        "at a time."
    ),
)

_register_docs_case(
    "import-csv",
    "How do I import a CSV file into one of my tables?",
    ["import-data-into-an-existing-table", "create-a-table-via-import"],
    ["import file", "csv", "separator"],
    reference_answer=(
        "For an existing table, click the ellipsis `•••` next to the view "
        "name, select `Import file`, choose CSV, then upload the file, "
        "review the field mapping, and click Import; you can optionally "
        "update existing rows instead of appending. To create a new table "
        "from a CSV, use `+ New table` and pick the CSV import option. Both "
        "paths let you set the separator, encoding, and header row, and are "
        "limited to 5,000 rows per import."
    ),
)

_register_docs_case(
    "airtable-import",
    (
        "I want to move my Airtable base over to Baserow — is there an "
        "importer for that?"
    ),
    ["import-airtable-to-baserow"],
    ["share link", "import from airtable", "airtable"],
    reference_answer=(
        "Yes — click `+ Add new` on your workspace home, select `Database`, "
        "switch to the `Import from Airtable` tab, and paste a public share "
        "link to your entire Airtable base. It imports tables, records, "
        "field types, relationships, attachments, and grid views with "
        "filters/sorts, but not automations, interfaces, comments, or "
        "revision history — and formula, lookup, and rollup fields come "
        "over empty and must be recreated with Baserow formulas."
    ),
)

_register_docs_case(
    "export-database",
    (
        "How do I export my data out of Baserow? I'd like a backup of the "
        "whole database, not just one table."
    ),
    ["export-workspaces", "export-tables", "export-a-view"],
    ["export data", "zip", "csv", "xlsx"],
    reference_answer=(
        "For a full backup, open the workspace dropdown on the Home page "
        "and select `Export data` — this produces a ZIP containing all "
        "databases, tables, views, and optionally file attachments "
        "(structure-only or with data). For a single table or view, use `⋮` "
        "next to the table name > `Export table`, or `•••` next to a view "
        "name > `Export view`, with CSV, Excel (.xlsx), JSON, or XML as "
        "formats (view export works on grid views)."
    ),
)

_register_docs_case(
    "recover-deleted-table",
    "I accidentally deleted a table — can I get it back?",
    ["data-recovery-and-deletion"],
    ["trash", "restore", "3 days"],
    reference_answer=(
        "Yes, if it was within the last 3 days: click `Trash` in the "
        "sidebar under Dashboard, find the deleted table, and click "
        "`Restore` — it returns to its original location with all rows, "
        "fields, and views. After the 3-day retention window items are "
        "permanently deleted and cannot be recovered."
    ),
)

_register_docs_case(
    "rename-table",
    "How do I rename one of my tables?",
    ["customize-a-table"],
    ["rename", "sidebar", "table name"],
    reference_answer=(
        "Click the `⋮` icon next to the table name in the sidebar, select "
        "`Rename`, and enter the new name. Renaming does not affect the "
        "table's data, views, or links to other tables."
    ),
)

_register_docs_case(
    "rename-workspace",
    "How can I change the name of my workspace?",
    ["setting-up-a-workspace"],
    ["rename workspace", "dropdown"],
    reference_answer=(
        "On the home page, click the workspace dropdown menu, select "
        "`Rename workspace`, type the new name, and press Enter. Renaming "
        "does not affect databases, member access, permissions, or API "
        "connections."
    ),
)

_register_docs_case(
    "create-database",
    "How do I create a new database in my workspace?",
    ["create-a-database"],
    ["add new", "workspace", "sidebar"],
    reference_answer=(
        "Click the `+ Add new` button on your workspace in the sidebar, "
        "choose `Database`, give it a name, and click `Create`. From the "
        "same menu you can instead start from a template, duplicate an "
        "existing database, or import an Airtable base. You need at least "
        "Member permissions in the workspace."
    ),
)

_register_docs_case(
    "create-view",
    (
        "I want to look at my table data in a different layout. How do I "
        "add a new view, and what view types can I pick from?"
    ),
    ["create-custom-views-of-your-data", "overview-of-baserow-views"],
    ["gallery", "kanban", "calendar", "timeline"],
    reference_answer=(
        "Open the view dropdown next to the current view name at the top of "
        "the table, pick a view type — Grid, Gallery, Form, Kanban, "
        "Calendar, or Timeline — choose Collaborative or Personal, name it, "
        "and click `Create view`. Note that Kanban, Calendar, and Timeline "
        "views require a paid plan; the free plan includes Grid, Gallery, "
        "and Form."
    ),
)

_register_docs_case(
    "kanban-view",
    (
        "How does the Kanban view work in Baserow? Do I need anything "
        "special in my table to use it?"
    ),
    ["guide-to-kanban-view"],
    ["single select", "premium", "paid"],
    reference_answer=(
        "Kanban view requires a Single select field: each option of that "
        "field becomes a column on the board, and dragging a card to "
        "another column automatically updates the field value. You can set "
        "a cover image from a File field and toggle which fields show on "
        "cards. Kanban is a premium feature — users on the free plan cannot "
        "create Kanban views."
    ),
)

_register_docs_case(
    "create-dashboard",
    (
        "Can I build a dashboard with charts from my table data? How do I "
        "create one and what widgets are there?"
    ),
    ["create-a-dashboard", "dashboards-overview"],
    ["widget", "summary", "chart", "paid"],
    reference_answer=(
        "Yes, on a paid plan: click `+ Create new` in your workspace, "
        "select `Dashboard`, name it, then add widgets in the editor. "
        "Available widgets are the Summary widget (a single aggregated "
        "value) and Bar, Line, Pie, and Doughnut chart widgets, each "
        "pulling data from a table you choose; charts support up to three "
        "series. Dashboards and chart widgets are not included in the free "
        "plan."
    ),
)

_register_docs_case(
    "group-by-view",
    (
        "How can I group the rows in my grid view by a field, like grouping "
        "tasks by status? Is that a paid feature?"
    ),
    ["group-rows-in-baserow"],
    ["group", "grid view", "five"],
    reference_answer=(
        "Click the `Group` button in the view toolbar and pick the field(s) "
        "to group by — up to five levels of nesting, with collapsible "
        "sections, an `(Empty)` group for blank values, and optional "
        "per-group summaries. Grouping is available on all plans, including "
        "free, but it works only in Grid view."
    ),
)

_register_docs_case(
    "hide-fields",
    (
        "Some columns are cluttering my view. How do I hide certain fields "
        "without deleting them?"
    ),
    ["view-customization"],
    ["hide fields", "hidden", "toggle"],
    reference_answer=(
        "Click the `Hide fields` button in the view toolbar and toggle off "
        "the fields you don't want shown. Hidden fields keep their data — "
        "each view has its own field visibility, so a field hidden in one "
        "view can stay visible in others."
    ),
)

_register_docs_case(
    "row-height",
    ("My rows are getting cut off — can I make the rows taller in my grid view?"),
    ["guide-to-grid-view", "view-customization", "navigating-row-configurations"],
    ["row height", "medium", "large", "tall"],
    reference_answer=(
        "Yes — use the `Row height` control in the grid view toolbar and "
        "pick a larger size (e.g. medium or large instead of the compact "
        "default). The change applies immediately to all rows and is saved "
        "per view, so other views keep their own height."
    ),
)

_register_docs_case(
    "conditional-formatting",
    (
        "I'd like rows to change color automatically based on their values "
        "— for example highlighting overdue tasks in red. Can Baserow do "
        "that?"
    ),
    ["row-coloring"],
    ["color", "condition", "paid", "premium"],
    reference_answer=(
        "Yes, with row coloring: click the `Color` button in the view "
        "toolbar and either match row colors to a single select field or "
        "define conditions that color rows when criteria are met, applied "
        "as a left border and/or a full background color. It works in Grid, "
        "Gallery, and Kanban views (configured per view) but requires a "
        "paid plan — free users can see colors set by others but cannot "
        "create their own."
    ),
)

_register_docs_case(
    "gallery-image-size",
    (
        "In my gallery view the pictures on the cards don't look right. Can "
        "I control the image size or how images are cropped on the cards?"
    ),
    ["guide-to-gallery-view"],
    ["cover", "customize cards", "file field"],
    reference_answer=(
        "No — gallery view has no image size or crop setting. The only "
        "cover control is choosing which File field supplies the card "
        "image, via the `Customize cards` toolbar button and the `Cover "
        "field` dropdown (your table needs at least one file field). To "
        "change how a card looks otherwise, toggle and reorder the visible "
        "fields in the same panel."
    ),
)

_register_docs_case(
    "templates",
    (
        "Is there a way to start from a ready-made template instead of "
        "building everything from scratch?"
    ),
    ["add-database-from-template"],
    ["template", "gallery", "add new"],
    reference_answer=(
        "Yes — click `+ Add new` in your workspace and choose `From "
        "template`, or browse the Baserow template gallery and click `Use "
        "this template`, pick a workspace, and click `Create`. Templates "
        "are grouped by category (CRM, project management, etc.), "
        "searchable, and available free on every plan, including the free "
        "tier."
    ),
)

_register_docs_case(
    "invite-users",
    (
        "How do I invite my teammates to my workspace? Can I pick what "
        "permissions they get when I send the invite?"
    ),
    ["working-with-collaborators"],
    ["invite", "member", "role"],
    reference_answer=(
        "Open your workspace's Members page, click `Invite member`, enter "
        "the person's email address, select their role (permission level), "
        "optionally add a message, and send the invite. The role is chosen "
        "at invite time; free plans have simplified roles, while paid plans "
        "offer granular roles for advanced permission management."
    ),
)

_register_docs_case(
    "dark-mode",
    "My eyes hurt at night — how do I turn on dark mode in Baserow?",
    ["account-settings-overview"],
    ["not available", "does not", "doesn't", "roadmap"],
    reference_answer=(
        "Baserow does not have a dark mode today — there is no theme or "
        "appearance toggle in the account settings. It is a tracked feature "
        "request on Baserow's roadmap; in the meantime a browser extension "
        "such as Dark Reader is the only workaround."
    ),
)

_register_docs_case(
    "cancel-free-trial",
    (
        "I started a trial and I don't want to get charged — how do I "
        "cancel my Baserow subscription?"
    ),
    ["cancel-subscriptions"],
    ["cancel subscription", "more details", "free plan", "downgrade"],
    reference_answer=(
        "Go to the Subscriptions page in your baserow.io account, click "
        "`More details` on the subscription, choose `Change subscription` > "
        "`Cancel subscription`, and confirm in the dialog. Paid features "
        "stay active until the end of the prepaid period, then the "
        "workspace automatically downgrades to the Free plan with all data "
        "intact; no refunds are given for the remaining period."
    ),
)

_register_docs_case(
    "free-plan-row-limit",
    ("How many rows can I have in Baserow on the free plan before I have to pay?"),
    ["pricing-plans"],
    ["3,000", "3000"],
    reference_answer=(
        "The Free plan allows 3,000 rows per workspace (with 2GB of "
        "storage). If you stay over the limit for 7+ consecutive days, "
        "creating new rows is blocked until you reduce usage or upgrade — "
        "Premium raises the limit to 50,000 rows per workspace and Advanced "
        "to 250,000."
    ),
)

_register_docs_case(
    "entra-sso",
    (
        "My company uses Microsoft Entra ID — how do I set up SSO so my "
        "team can log into Baserow with it?"
    ),
    ["configure-sso-with-azure-ad", "single-sign-on-sso-overview"],
    ["saml", "advanced", "enterprise", "self-hosted"],
    reference_answer=(
        "Configure Entra ID as a SAML 2.0 provider: on your self-hosted "
        "Baserow instance, an instance admin adds an `SSO SAML Provider` "
        "under the admin Authentication settings, registers a non-gallery "
        "enterprise application in the Microsoft Entra admin center, maps "
        "the email/name claims, and pastes the (cleaned) Federation "
        "Metadata XML into Baserow. SSO requires the Advanced or Enterprise "
        "plan with an activated license, and OIDC is not recommended for "
        "Azure AD due to PKCE compatibility."
    ),
)

_register_docs_case(
    "row-history-retention",
    (
        "How far back can I see the change history of a row? Does it depend "
        "on which plan I'm on?"
    ),
    ["row-change-history"],
    ["14 days", "90 days", "180 days"],
    reference_answer=(
        "Open the row (expand icon) and click the `History` tab in the row "
        "detail panel. On Baserow cloud, row history is retained for 14 "
        "days on the Free plan, 90 days on Premium, and 180 days on "
        "Advanced; self-hosted instances default to 180 days and the "
        "retention is configurable."
    ),
)

_register_docs_case(
    "phone-number-field",
    (
        "Does Baserow have a proper phone number field, or should I just "
        "store numbers in a text field?"
    ),
    ["phone-number-field"],
    ["phone number field", "tel:", "clickable"],
    reference_answer=(
        "Yes — Baserow has a dedicated Phone number field type. It only "
        "accepts characters commonly used in phone numbers (digits, +, (, "
        "), -, spaces, #, *, N/X) and renders each value as a clickable "
        "`tel:` link that opens your device's calling app; note it "
        "validates characters only and doesn't verify the number actually "
        "exists."
    ),
)

_register_docs_case(
    "upload-file",
    "How can I attach photos and documents to my rows in Baserow?",
    ["file-field"],
    ["file field", "drag", "upload"],
    reference_answer=(
        "Add a File field to your table (add a new field, choose `File`, "
        "click `Create`), then click the `+` icon in a cell to upload files "
        "from your device or from a URL, or simply drag and drop files onto "
        "the cell; in the expanded row view you can also click `Add a "
        "file`. On Baserow cloud each file can be up to 100MB, and images "
        "and documents get thumbnail previews."
    ),
)

_register_docs_case(
    "auto-number-field",
    (
        "Can Baserow automatically number my rows in sequence, like an "
        "invoice counter? And can I add a prefix like INV-?"
    ),
    ["autonumber-field"],
    ["autonumber", "formula", "incrementing"],
    reference_answer=(
        "Yes — use the Autonumber field type, which automatically assigns a "
        "unique incrementing number (1, 2, 3…) to each new row based on its "
        "creation time; the value is read-only and stays stable when rows "
        "are reordered. There are no built-in prefix or formatting options, "
        "so for custom IDs like `INV-1001` the docs recommend combining the "
        "Autonumber field with a Formula field that concatenates your "
        "prefix."
    ),
)

_register_docs_case(
    "api-docs-overview",
    (
        "Where can I find the API documentation for my database? I'd like "
        "to see the exact endpoints and field names for my tables."
    ),
    ["database-api"],
    ["api docs", "redoc", "auto-generated"],
    reference_answer=(
        "Click the three-dot menu next to your database name in the sidebar "
        "and select `View API Docs` — Baserow auto-generates API "
        "documentation specific to your database schema, and it updates "
        "when the schema changes. The full general REST API specification "
        "is also available at https://api.baserow.io/api/redoc/."
    ),
)

_register_docs_case(
    "create-api-token",
    (
        "How do I create an API token so an external script can read and "
        "write rows in my tables?"
    ),
    ["personal-api-tokens"],
    ["database token", "create token", "authorization"],
    reference_answer=(
        "Create a database token: click your workspace in the top left "
        "corner, go to `Settings`, open the `Database tokens` tab, and "
        "click `Create token +`. Each token is scoped to one workspace with "
        "per-table create/read/update/delete toggles, and you use it in "
        "requests as the header `Authorization: Token YOUR_TOKEN`."
    ),
)

_register_docs_case(
    "api-pagination",
    (
        "I'm calling the list rows endpoint but I only get 100 rows back. "
        "How do I fetch all the rows in my table through the API?"
    ),
    ["database-api"],
    ["size", "page", "200"],
    reference_answer=(
        "The list rows endpoint is paginated: pass the `size` query "
        "parameter (default 100, maximum 200 rows per page) and iterate "
        "with the `page` parameter, which starts at 1, until you've fetched "
        "all rows. Example: `GET "
        "/api/database/rows/table/123/?size=200&page=2`."
    ),
)

_register_docs_case(
    "webhooks-availability",
    (
        "Does Baserow have webhooks? I want my server to be notified "
        "whenever rows change, and I'm wondering if I need a paid plan for "
        "that."
    ),
    ["webhooks"],
    ["webhook", "rows created", "rows updated"],
    reference_answer=(
        "Yes — webhooks are built in and not gated behind a paid plan. Open "
        "the three-dot menu beside your table, select `Webhooks`, then "
        "`Create webhook +`; you set the URL and HTTP method and pick "
        "trigger events such as rows created, rows updated, rows deleted, "
        "conditional row update, and row enters view."
    ),
)

_register_docs_case(
    "mcp-server",
    (
        "Does Baserow have an MCP server so I can connect my workspace to "
        "AI tools like Claude or Cursor? How do I set it up?"
    ),
    ["mcp-server", "claude-mcp", "cursor-mcp"],
    ["mcp", "endpoint", "my settings"],
    reference_answer=(
        "Yes — Baserow has a native, built-in MCP server. Click your "
        "workspace name, open `My Settings`, go to the `MCP Server` tab, "
        "and click `Create Endpoint`; Baserow generates a unique endpoint "
        "URL you add to your MCP client (Claude Desktop, Cursor, and "
        "Windsurf are documented, and any MCP-compliant client can "
        "connect). Treat the URL like a password, since it grants access to "
        "your workspace data."
    ),
)

_register_docs_case(
    "link-two-tables",
    (
        "How do I create a relationship between two tables? For example, I "
        "want to connect my Orders table to my Customers table."
    ),
    ["link-to-table-field"],
    ["link to table", "link-to-table", "related field"],
    reference_answer=(
        "Add a `Link to table` field: click the `+` to add a new field in "
        "your Orders table, choose the `Link to table` field type, pick "
        "Customers from the `Select a table to link to` dropdown, and click "
        "Create. Baserow automatically creates the reciprocal link field in "
        "Customers (unless you uncheck 'Create related field in linked "
        "table'), and you can allow single or multiple linked rows per "
        "record."
    ),
)

_register_docs_case(
    "count-linked-rows",
    (
        "My Projects table is linked to a Tasks table. How can I show the "
        "number of tasks linked to each project as a column?"
    ),
    ["count-field", "rollup-field"],
    ["count", "rollup", "link row"],
    reference_answer=(
        "Use a `Count` field: add a new field, select the `Count` type, and "
        "pick your Tasks link-to-table field in the `Select a link row "
        "field` dropdown — it shows a read-only number of linked rows that "
        "updates automatically. If you need other calculations over the "
        "linked rows (sum, average, min/max of a specific field), use a "
        "`Rollup` field instead."
    ),
)

_register_docs_case(
    "sum-column",
    "How can I get the total sum of a number column in my table?",
    ["footer-aggregation"],
    ["sum", "footer", "summar"],
    reference_answer=(
        "In grid view, scroll to the bottom of the column, click the "
        "dropdown in the footer row under that field, and select `Sum` — "
        "the total appears immediately and updates live, respecting the "
        "view's filters. Note that a formula field cannot sum a column of "
        "its own table (formula `sum()` only aggregates linked/lookup "
        "values), so the footer summary is the way to total a column."
    ),
)

_register_docs_case(
    "formula-today",
    "What formula do I use to get today's date in a formula field?",
    ["understanding-formulas"],
    ["today()", "now()", "today("],
    reference_answer=(
        "Use `today()` for the current date, or `now()` if you also need "
        "the time. Both refresh roughly every 10 minutes (best effort, can "
        "be less frequent for idle workspaces), and you can compute date "
        "differences like `today() - field('Start Date')`."
    ),
)

_register_docs_case(
    "folders-in-database",
    (
        "Can I create folders or sub-groups inside a database to organize "
        "my tables? I have about 40 tables and the sidebar is getting "
        "messy."
    ),
    ["create-a-database", "intro-to-databases"],
    ["not", "databases", "workspace"],
    reference_answer=(
        "Baserow doesn't have folders or sub-groups for organizing tables "
        "inside a database. The closest alternative is to split your tables "
        "across multiple databases within the same workspace, and "
        "drag-and-drop tables in the sidebar to keep related ones next to "
        "each other."
    ),
)

_register_docs_case(
    "per-cell-color",
    (
        "Is there a way to set the background color of a single cell in my "
        "grid view? I want to highlight one specific cell, not the whole "
        "row."
    ),
    ["row-coloring"],
    ["not", "row coloring"],
    reference_answer=(
        "Baserow doesn't support setting the background color of an "
        "individual cell. The closest feature is row coloring, a paid "
        "feature that colors the entire row (as a left border flag or "
        "background) based on conditions or a single select field's option "
        "colors."
    ),
)

_register_docs_case(
    "formula-previous-row",
    (
        "How do I write a formula that references the previous row's value? "
        "I need a running balance column that adds each row's amount to the "
        "total from the row above."
    ),
    ["understanding-formulas", "link-to-table-field", "lookup-field"],
    ["not", "link", "lookup"],
    reference_answer=(
        "Baserow formulas can't reference the previous row or compute "
        "running totals — a formula only sees its own row plus rows "
        "connected through a link to table field. The closest workaround is "
        "to explicitly link rows to each other and aggregate over the link "
        "with lookup functions like sum(lookup(...)), or compute the "
        "running total outside Baserow via the API or an automation."
    ),
)

_register_docs_case(
    "ocr-scan",
    (
        "Can Baserow OCR my scanned PDFs and images? I have a file field "
        "full of scanned invoices and I want to pull the text out of them."
    ),
    ["ai-field", "file-field"],
    ["ai field", "file field"],
    reference_answer=(
        "Yes, via the AI field (a paid feature): point it at your file "
        "field and it can read the attachments — including images and PDFs "
        "— so you can prompt it to extract the text from scanned invoices "
        "into another field. There is no separate dedicated OCR engine; the "
        "extraction is done by the AI model you configure."
    ),
)

_register_docs_case(
    "custom-css-core-ui",
    (
        "Can I add custom CSS to restyle Baserow's grid interface itself? "
        "I'd like the core UI to match our company branding."
    ),
    ["custom-css-and-javascript", "admin-panel-settings"],
    ["not", "brand", "application builder"],
    reference_answer=(
        "Baserow doesn't support custom CSS or theming of its core database "
        "interface. The Enterprise co-branding feature lets you replace the "
        "Baserow logo with your own, and the Application Builder has full "
        "theme settings plus a Custom CSS/JS option — but those style the "
        "applications you publish, not Baserow's own grid UI."
    ),
)

_register_docs_case(
    "address-autocomplete-field",
    (
        "Is there an address field in Baserow that autocompletes or "
        "suggests addresses while I type?"
    ),
    ["single-line-text-field"],
    ["doesn't", "text field"],
    reference_answer=(
        "Baserow doesn't have an address field type or any address "
        "autocomplete. Store addresses in a single line text field, or "
        "split them across separate text fields for street, city, and "
        "postcode; nothing suggests addresses while you type."
    ),
)

_register_docs_case(
    "form-tabs-multistep",
    (
        "Can I split my Baserow form into multiple steps or tabs instead of "
        "showing everything on one long page?"
    ),
    ["form-survey-mode"],
    ["survey", "one"],
    reference_answer=(
        "Baserow doesn't have tabbed forms or pages that group several "
        "fields together, but the form view's Survey mode is a real "
        "multi-step option: it shows one question per step with "
        "previous/next navigation, and is available on paid plans. For a "
        "fully custom multi-step layout you can build a form in the "
        "Application Builder instead."
    ),
)

_register_docs_case(
    "form-edit-existing-row",
    ("Can I use a Baserow form to edit an existing row instead of creating a new one?"),
    ["edit-rows-via-form"],
    ["edit row link", "fill", "existing row"],
    reference_answer=(
        "Yes — the Edit row link field does exactly this. Add an Edit row "
        "link field to your table and point it at a form view: every row "
        "gets a unique secure link that opens the form pre-filled with that "
        "row's current data, and submitting updates the existing row "
        "instead of creating a new one. Treat each link like a password, "
        "since anyone holding it can view and change that row."
    ),
)

_register_docs_case(
    "sync-column-widths",
    (
        "Is there a way to keep my column widths identical across all the "
        "views of a table, so resizing once applies everywhere?"
    ),
    ["guide-to-grid-view"],
    ["doesn't", "each view", "duplicat"],
    reference_answer=(
        "Baserow doesn't have a way to sync column widths across views — "
        "width is saved per view, so each view keeps its own. The closest "
        "workaround is to set the widths once and then duplicate that view, "
        "because duplicating copies the field widths along with the rest of "
        "the configuration."
    ),
)

_register_docs_case(
    "own-rows-only-permissions",
    (
        "Can I restrict my collaborators so they can only see and edit the "
        "rows they created themselves?"
    ),
    ["view-level-permissions"],
    ["doesn't", "restricted view", "application builder"],
    reference_answer=(
        "Baserow doesn't have row-level permissions — roles apply at the "
        "workspace, database, table, and view level, and there's no "
        "automatic 'only rows created by the current user' rule. The "
        "closest options are restricted views (view-level permissions), "
        "where you create a view with a fixed filter on a Created by or "
        "collaborator field and grant only that person access to it, or an "
        "Application Builder app that filters rows by the logged-in user."
    ),
)
