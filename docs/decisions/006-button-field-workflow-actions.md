# How the Button Field Shares Workflow Actions Across Modules

See this issue for background: https://github.com/baserow/baserow/issues/1722

The button field introduces a read-only field type whose cells render a button. When
clicked, an ordered sequence of actions is executed with the clicked row available as
context, and each action's result available to the following actions.

Baserow already has two implementations of "execute configured actions backed by
services":

*   The application builder has `BuilderWorkflowAction`, which subclasses the abstract
    `baserow.core.workflow_actions.models.WorkflowAction`. It mixes service-backed
    actions (create row, send email, ...) with browser-only actions (open page,
    logout) and ties actions to a page/element/event.
*   The automation module deliberately did **not** reuse this. There is no
    `AutomationWorkflowAction`; instead `AutomationNode` holds a
    `OneToOneField(Service)` and models execution as a graph of nodes with edges and
    previous-node outputs.

The button field would be the third consumer of this concept, so we should decide
whether to add a third module-specific implementation or consolidate first.

# Decision

Option 1 is proposed (pending discussion with the builder and automation teams):

-   The core abstraction we would consolidate around already exists
    (`baserow.core.workflow_actions`), and the builder proves it works for
    element-triggered, ordered, service-backed actions, which is exactly the button
    field's shape.
-   All button field actions are service-backed, so the service layer (which is the
    expensive part: request handling, integrations, dispatch) is already shared. What
    gets duplicated in Option 1 is the thin module-specific layer: the model FK
    target, the registry, and the execution loop.
-   Consolidating first (Option 3) blocks an XL feature on a cross-team refactor of
    two shipped modules, and we do not yet know what the right shared abstraction is.
    The button field will give us a third data point; extracting the common parts
    afterwards is easier than guessing them upfront.
-   Automation's graph model (Option 2) is more machinery than the button field needs.
    A button runs a flat, ordered list. If routers/branching are ever needed, that is
    the moment to revisit.

To keep the eventual consolidation cheap, the implementation should:

-   Keep the database-specific layer as thin as the builder's: a
    `DatabaseWorkflowAction` subclassing the core `WorkflowAction`, with an FK to the
    button field and an `order` field.
-   Only allow service-backed action types. No database equivalent of the builder's
    browser-only actions.
-   Model the "previous action result" data provider on the existing
    `PreviousActionProviderType` (builder) / `PreviousNodeProviderType` (automation)
    pair rather than inventing a third shape, so the three can later be merged.

Revisit trigger: if a fourth consumer of this concept appears, or if the button field
needs branching/routers, extract a shared executable action-sequence abstraction into
core instead of copying again.

## Option 1: Database-scoped `DatabaseWorkflowAction`, following the builder pattern

Add `contrib/database` workflow actions that subclass the existing abstract core
`WorkflowAction`, with a registry and handler mirroring
`contrib/builder/workflow_actions/`. Actions belong to a button field and hold an FK
to a `Service`. Execution walks the ordered actions, dispatching each service with a
dispatch context that exposes the clicked row
(`HumanReadableFieldsDataProviderType`, already used by the AI field) and previous
action results.

### Pros

-   Proven pattern; the core base model, registry mixins, and import/export support
    already exist.
-   Fastest path to shipping; no changes to builder or automation.
-   Module isolation: database does not gain a dependency on builder or automation
    internals.
-   Recommended by the builder/automation maintainers in the issue discussion.

### Cons

-   Third implementation of the execution loop and previous-result context chaining.
-   The known reason automation could not reuse the builder's implementation is not
    addressed, only worked around.

## Option 2: Node/service model, following the automation pattern

Give the button field an ordered list of records that each hold a
`OneToOneField(Service)`, like `AutomationNode`, skipping the `WorkflowAction` base
entirely.

### Pros

-   All button actions are service-backed, which matches automation's "every node is
    a service" invariant better than the builder's mixed model.
-   Could later inherit automation features such as routers/edges and run history.

### Cons

-   `AutomationNode` is coupled to workflows and graph traversal (edges, previous
    node outputs); reusing it requires extracting those parts first, which is a
    refactor of a shipped module.
-   A flat ordered list does not need graph machinery.
-   Diverges from the core `WorkflowAction` abstraction instead of converging on it.

## Option 3: Extract a shared action-sequence abstraction into core first

Before building the button field, refactor so core owns an executable "ordered,
service-backed action sequence with context chaining" (models, execution loop,
previous-result provider), then port builder and automation to it and build the
button field on top.

### Pros

-   One implementation of execution and context chaining instead of three.
-   Fixes the abstraction deficiency that already forced automation to opt out.
-   Future consumers (e.g. dashboard actions) become cheap.

### Cons

-   Large cross-team refactor of two shipped modules, with migration risk, blocking
    an XL feature on work that delivers no user-facing value by itself.
-   We would be designing the shared abstraction from only two (soon three) partially
    understood use cases; a wrong guess here is expensive to reverse after
    migrations ship.
