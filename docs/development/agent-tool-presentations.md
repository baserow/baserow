# Agent tool presentations

Tool activity uses Core's `toolPresentation` registry and shared chat cards.
Workspace tools and configured actions use the same UI, live and after reload.
The Agent module registers its database presenters in `modules/agent/plugin.js`;
other modules can register presenters without changing the card renderer.

See [Background chat runs](./background-chat-runs.md) for the streaming lifecycle.

## The step contract

The backend emits `step` events and saves the same steps on the assistant message:

```json
{
    "id": "unique-call-id",
    "tool": "create_rows",
    "presentation_type": "create_rows",
    "status": "running",
    "changes_data": true,
    "input": {
        "requested_count": 1,
        "values": { "table_id": 42, "rows": [{ "Name": "Planning" }] }
    },
    "facts": {}
}
```

`presentation_type` is a stable presentation key. `tool` identifies the execution
tool; a configured action may have a dynamic name such as `action_37` while using
the stable `send_email` presenter. Presentation keys never select execution or
grant permissions. Older steps without `presentation_type` resolve through
`tool`. Step IDs identify individual calls, including repeated calls to one tool.

`input` contains a display summary derived from arguments, such as a requested
count. Mutation tools can also supply `input.values`: an explicitly allowed,
bounded preview of the requested input. Database changes include identifiers,
row values, field definitions and filter values so users can inspect the change.
Read tools retain only their summaries. Never copy all arguments automatically:
future action tools must select user-facing values and exclude credentials,
provider configuration and internal context. `facts` contains confirmed outcomes, such as
`{"count": 2, "table": "Tasks"}`, extracted after authorized success. Names must
come from authorized results or permitted lookups. Requested counts do not prove
how many items changed: reuse and partial results can produce different counts.

Agent tools define these summaries with `AgentToolType.get_step_input(arguments)`
and `get_step_facts(ctx, arguments, result)`. Invalid or unavailable summaries
remain empty. Summary extraction must never change whether execution succeeds.
Input previews travel with the step through streaming, persistence and reload;
they describe the request, not a guarantee of what changed. Older saved steps
without `values` keep a non-expandable action card.

Use Core's `tool_input_preview` after selecting the allowed values. It copies
them without changing the executed arguments, limits the preview to 16 KiB of
compact JSON, 500 nodes, eight nested levels and 1,000 characters per string,
and marks omissions with `truncated: true`. Invalid JSON values are replaced or
omitted. This bounds display and storage costs; it does not decide which fields
are safe to display.

Unexpected tool and summary failures use Core's `report_exception` helper. When
Sentry is configured, it captures the original exception, traceback locals and
tool context, subject to the existing scrubbing and size limits. Console logs
contain only a safe summary, exception class and Sentry event ID when available.
The fake Sentry console transport also uses that safe summary. Reporting failures
must preserve the tool result and empty-summary fallback.

The frontend uses `STEP_STATUS` from `modules/core/chatRuns/constants.js` for
the statuses `running`, `done`, `failed` and `stopped`. `stopped` means the
outcome is uncertain; a write may already have completed. It does not imply
rollback. Missing history steps are supported and produce no activity cards.
Workspace groups show a spinner while any call is running. Once settled, the
summary reflects the last call in display order. Every expanded line has its own
status icon, so earlier failed or interrupted calls remain visible without
making a later successful call look unsuccessful.

Failed steps may include `error_code`: `not_found`, `permission_denied`,
`invalid_input`, `partial_failure` or `failed`. Use backend `ChatRunStepErrorCode`
and frontend `STEP_ERROR_CODE` constants. Exception categories are passed through
`ToolReturn.metadata`; Core only copies recognized codes into failed steps.
Validation retries and incomplete batch results receive fixed categories too.
The shared card translates these codes into hover tooltips on warning icons and
includes the same explanation in screen-reader text. Missing or unknown codes
use a generic failure hint. No raw error messages are included, and Sentry
diagnostics are unchanged. The existing tooltip is hover-only; no new popover or
interaction model is introduced. These optional codes persist in the same JSON
steps without a migration; old messages do not gain a reconstructed reason.

## Registering a presenter

Extend `ToolPresentationType` from `modules/core/toolPresentationTypes.js` and
register it from the owning module's plugin, after Core initializes its namespace.
This example shows a future email action's presentation only; it does not send mail:

```javascript
import { ToolPresentationType } from "@baserow/modules/core/toolPresentationTypes";
import { STEP_STATUS } from "@baserow/modules/core/chatRuns/constants";

class EmailToolPresentationType extends ToolPresentationType {
    static getType() {
        return "send_email";
    }

    getLabel(t) {
        return t("emailTool.send");
    }

    getActivity({ status, facts }, t) {
        if (status === STEP_STATUS.RUNNING) return t("emailTool.sending");
        if (status === STEP_STATUS.DONE && facts.delivery === "sent") {
            return t("emailTool.sent");
        }
        if (status === STEP_STATUS.DONE && facts.delivery === "queued") {
            return t("emailTool.queued");
        }
        return this.getLabel(t);
    }

    getInput({ input }) {
        // The backend explicitly selected user-facing email fields, e.g.
        // recipients, subject and body. It must never include SMTP credentials.
        return input;
    }
}

export default defineNuxtPlugin({
    name: "email-tools",
    dependsOn: ["core"],
    setup(app) {
        app.$registry.register(
            "toolPresentation",
            new EmailToolPresentationType({ app }),
        );
    },
});
```

The base also provides `icon`, `getDescription(t)`, `getInput(step, t)` and `group`.
`getInput` defaults to `null`; opt in by returning the backend's
`{ values, truncated? }` preview. Core validates the preview independently of the
title, so invalid or oversized input cannot hide the activity. Leave `group` as
`null` for actions. Only workspace reads should return `WORKSPACE_TOOL_GROUP`
from `modules/core/toolPresentationTypes.js`.
`groupToolSteps(steps, registry, t)` groups consecutive workspace reads and gives
each write or action its own card, even when an action is read-only.
`ChatStepGroup` renders the resulting title, status and optional activity lines.
Action inputs use the same card and caret, initially collapsed. Expanded previews
show escaped, formatted JSON and a notice when `truncated` is true.
`toolActivity(step, registry, t)` supplies individual labels, including composer
activity. Unknown presenters, missing translations and formatter exceptions use
generic labels while preserving status; unknown presenters never display inputs.

## Translations and coverage

Put labels in the owning module's English locale file. Core owns generic fallback,
workspace-group and status labels. Use complete translated sentences and Vue i18n
plural forms, for example `"Creating {count} row | Creating {count} rows"`, called
with `t(key, { count }, count)`. Missing counts use action-only labels. A queued
email must say queued rather than sent. Agent permission settings reuse presenter
labels, while permission groups remain Agent-owned.

Add each tool to `tests/cases/agent_tools.json` with its execution name, stable
presentation key, valid example arguments, expected `input` and representative
`facts`. Backend tests compare examples with the actual tool registry, validate
argument schemas and check summary extraction. Frontend tests compare the fixture
with the actual registered presenters and exercise real English translations.
Both CI path filters include the shared fixture. A runtime fallback does not
exempt a new tool from presenter coverage.
The fixture's `step_error_codes` also keeps backend/frontend constants in sync.

Future action-tool registrations must join these contract checks using their
stable presentation key. Cover only services that can actually become tools.
Add focused tests for argument summaries, confirmed outcomes, plural forms and
fallback behavior. The existing synthetic email presenter test demonstrates that
an action uses the shared presentation path without database-specific rendering.
