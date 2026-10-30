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
    "input": { "requested_count": 3 },
    "facts": {}
}
```

`presentation_type` is a stable presentation key. `tool` identifies the execution
tool; a configured action may have a dynamic name such as `action_37` while using
the stable `send_email` presenter. Presentation keys never select execution or
grant permissions. Older steps without `presentation_type` resolve through
`tool`. Step IDs identify individual calls, including repeated calls to one tool.

`input` contains a small display summary derived from arguments, such as a
requested count. It must exclude row values, search text, credentials, formulas
and complete argument objects. `facts` contains confirmed outcomes, such as
`{"count": 2, "table": "Tasks"}`, extracted after authorized success. Names must
come from authorized results or permitted lookups. Requested counts do not prove
how many items changed: reuse and partial results can produce different counts.

Agent tools define these summaries with `AgentToolType.get_step_input(arguments)`
and `get_step_facts(ctx, arguments, result)`. Invalid or unavailable summaries
remain empty. Summary extraction must never change whether execution succeeds.

The frontend uses `STEP_STATUS` from `modules/core/chatRuns/constants.js` for
the statuses `running`, `done`, `failed` and `stopped`. `stopped` means the
outcome is uncertain; a write may already have completed. It does not imply
rollback. Missing history steps are supported and produce no activity cards.

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

The base also provides `icon`, `getDescription(t)` and `group`. Leave `group` as
`null` for actions. Only workspace reads should return `WORKSPACE_TOOL_GROUP`
from `modules/core/toolPresentationTypes.js`.
`groupToolSteps(steps, registry, t)` groups consecutive workspace reads and gives
each write or action its own card, even when an action is read-only.
`ChatStepGroup` renders the resulting title, status and optional activity lines.
`toolActivity(step, registry, t)` supplies individual labels, including composer
activity. Unknown presenters, missing translations and formatter exceptions use
generic labels while preserving status; they never display raw arguments/results.

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

Future action-tool registrations must join these contract checks using their
stable presentation key. Cover only services that can actually become tools.
Add focused tests for argument summaries, confirmed outcomes, plural forms and
fallback behavior. The existing synthetic email presenter test demonstrates that
an action uses the shared presentation path without database-specific rendering.
