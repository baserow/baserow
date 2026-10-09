# ADR 010: Group reusable agents in workspace applications

|              |                                                |
| ------------ | ---------------------------------------------- |
| Status       | Proposed                                       |
| Date         | 2026-10-09                                     |
| Issue        | https://github.com/baserow/baserow/issues/6259 |
| Author       | Davide Silvestri (@silvestrid)                 |
| Contributors | To be confirmed                                |

## Summary

Users need reusable agents whose creation, configuration and use can be controlled
through Baserow's RBAC and whose tools reuse existing capabilities. We will introduce
an Agent Builder workspace application containing one or more independently configured
and permissioned agents, following the database and tables model.

## Context

Baserow organizes databases and tables, builders and pages, and automations and workflows
under workspace applications. These provide management and portability entry points, but
each application type must implement the preservation of its own content.

The [permissions system](../technical/permissions-guide.md) supports operations on
objects in a hierarchy, with inherited roles and assignments at narrower scopes. Shared
integration and service types implement connections, input resolution and backend
workflow actions. These building blocks are available to new application types too.

The requirements driving this choice are:

- Control agent creation, configuration and invocation through application roles and
  individual agent assignments, as for databases and tables.
- Reuse an agent from conversations and automatic jobs without copying its definition
  into each entry point.
- Reuse internal tools and service-backed workflow actions, including their permissions
  and connections.
- Let users organize related agents and recover or share their supported configuration
  through familiar application operations.

This record chooses the ownership and reuse boundary. The launch catalogue, execution
engine, approvals and multi-agent orchestration are separate decisions. The
[delivery issue](https://github.com/baserow/baserow/issues/6259) defines release scope.

| Term               | Meaning                                                                                               |
| ------------------ | ----------------------------------------------------------------------------------------------------- |
| Agent application  | The Agent Builder workspace application that groups related agent definitions.                        |
| Agent definition   | A reusable child object with its own instructions, tool configuration and supported entry points.     |
| Execution identity | The actor whose permissions and connections govern effects performed by an agent.                     |
| Agent team         | A group of agent definitions in an application; it does not imply autonomous delegation or execution. |

Baserow's existing core `Agent` is a workspace-owned permission subject: it can serve as
an execution identity, but is distinct from the configurable agent definition above.

## Decision

### 1. One application can contain several agents

Each agent definition belongs to one Agent Builder application and has independent
configuration. Supported callers, including conversations and triggers, select it by ID
instead of owning copies. A single-agent application uses the same structure.

### 2. Use the existing permission hierarchy

Use application and child-agent scopes and operations in the existing permission system,
with inherited application roles and individual agent assignments. Separate application
creation, agent creation, configuration, invocation and conversation/run visibility. A
user can use an agent without editing it or reading another person's conversation.

Enforce permissions in backend APIs, lists and realtime events. A user assigned to one
child can navigate to it without seeing unauthorized siblings. Application membership
does not implicitly share conversations, memory or execution authority between agents.

Invocation does not make the caller the execution identity or grant direct access to
tool resources. Check current resource permissions and tool policies under the authorized
execution identity when tools run, including after resuming suspended work.

### 3. Adapt shared capabilities instead of duplicating them

Adapt existing internal tool implementations and supported backend service types as agent
tools. Reuse input/formula resolution, dispatch and result handling. Frontend-only actions
and services requiring a particular workflow context need separate qualification.

Implementation reuse does not grant access to another application's actions or
credentials. Respect integration ownership and authorization, requiring configuration or
reconnection where needed. Automations can invoke agents by reference without owning them.

### 4. Honor the shared application lifecycle

Support duplication, export/import, templates, snapshots, trash/restore and deletion for
owned configuration. Remap references, honor permissions and sensitive-data options, and
report missing dependencies. Copies and snapshot restorations create independent
applications with automatic entry points disabled until explicitly enabled.

Copies exclude ordinary private conversations, live executions and pending approvals.
Trash prevents starting or resuming work; deletion preserves shared dependencies and
identities. Restoring configuration does not reverse external effects.

## Options considered

All options can use the permission system and shared service implementations. The
comparison is about the ownership, permission hierarchy and lifecycle work each requires.

### Agent Builder application with child agents — selected

Groups related agents, roles and integrations while permitting child assignments, like
tables in a database. Related agents can be copied or installed together. Costs include
child scopes, filtered navigation and preserving every agent in lifecycle operations;
independently running agents still share a packaging boundary.

### One workspace application per agent

Provides direct application roles and independent copy, snapshot and deletion boundaries
with fewer new hierarchy concepts. Related agents become separate sidebar entries and
assignments; coordinated reuse needs another grouping mechanism. Prefer this if
independent agent lifecycles matter more than managing a related set.

### Standalone workspace-owned agent definitions

Offers discovery across applications and direct workspace ownership. RBAC and shared
services remain possible, but navigation, snapshots, templates, trash and integration
ownership need new entry points or adapters. This adds a parallel lifecycle without a
current requirement for a workspace-wide live catalogue.

### Agents owned by Automation workflows or nodes

Reuses AI agent actions, service dispatch and event-driven execution. Fits a task confined
to one workflow, but couples a reusable agent's ownership and lifecycle to that workflow.
Independent conversations and callers would need a separate definition anyway. Keep
workflows as possible callers.

### Configurable profiles inside the existing assistant

Reuses conversation UI and internal tools; suits personal customization. Independent
creation/invocation permissions, delegated identities, automatic entry points and portable
configuration would require another managed resource model. Reuse assistant components
without making the assistant the ownership boundary.

## Consequences

- Users can treat an application as an agent team: one place to find, configure and use
  related agents, analogous to navigating tables in a database. A future team entry point
  could route a request to the appropriate permitted agent, reducing the need to choose
  among many agents. Routing, delegation or a swarm must preserve each agent's access
  and execution identity; grouping alone does not introduce those capabilities.
- Application roles reduce repeated administration, while child roles keep agents
  independently accessible. This requires filtered navigation and separate conversation
  and run visibility, rather than treating access to the group as access to everything.
- Shared tool and service implementations reduce duplicated connection and execution
  logic. Adapters, supported catalogues and permission checks still require maintenance;
  sharing an application does not authorize every agent to use every connection.
- The application becomes the boundary for packaging and recovery. Moving an agent to
  another application or releasing it independently requires handling its references,
  integrations and inherited roles explicitly.
- Lifecycle support is part of releasing each capability. We must verify real round
  trips, denied access, missing dependencies and inactive copies; a snapshot cannot
  recover external effects or historical versions of shared workspace resources.

## Revisit triggers

- Customers need one live agent definition shared across applications or workspaces,
  with updates propagated to all callers instead of independent installed copies.
- Independent versioning, promotion between environments, transfer of ownership or
  recovery of individual agents becomes more common than managing a team together.
- Permission assignment or navigation for large agent groups becomes too costly or
  confusing, and measured usage favors a workspace-wide catalogue or another hierarchy.
- An agent must belong to several independently governed teams, or delegation needs
  relationships and recovery across application boundaries that one owner cannot represent.
- Reusing configured actions and connections across applications becomes a core need
  that cannot be met cleanly by the existing integration ownership model.
- Agent execution must move to independently deployed runtimes or support external
  agent definitions whose identity and lifecycle Baserow applications cannot own.
