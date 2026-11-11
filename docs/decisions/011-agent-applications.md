# ADR 011: Represent each agent as a workspace application

|              |                                                |
| ------------ | ---------------------------------------------- |
| Status       | Proposed                                       |
| Date         | 2026-10-12                                     |
| Issue        | https://github.com/baserow/baserow/issues/6259 |
| Author       | Davide Silvestri (@silvestrid)                 |
| Contributors | Bram Wipjes                                    |

## Summary

Agents need an ownership model that makes them easy to create, configure and manage.
We considered an Agent Builder (option 1), which contains many agents, and an agent
application (option 2), which is exactly one agent. We choose the agent application to
prioritize a simple starting experience and independent management.

## Terms

| Term                         | Meaning                                                                                             |
| ---------------------------- | --------------------------------------------------------------------------------------------------- |
| Agent                        | A reusable, configured AI agent that callers can invoke.                                            |
| `Agent` subject              | The core permission subject with a workspace role. An agent may run as one: its execution identity. |
| Caller                       | Anything that references an agent to invoke it, such as a conversation or an automatic job.         |
| Agent Builder (option 1)     | A workspace application containing many agents, as a database contains tables.                      |
| Agent application (option 2) | A workspace application of type `agent` that is exactly one agent.                                  |
| Related agents               | Agents a team wants to manage together, such as all support agents.                                 |
| Lifecycle operations         | Duplicate, export/import, snapshot, trash and restore.                                              |
| Workspace integration        | A planned integration owned by the workspace, so several applications can share its secrets.        |

## Context

Baserow organizes related resources within workspace applications: databases contain
tables, Application Builders contain pages, and Automations contain workflows. These
applications provide a common boundary for navigation, permissions and lifecycle
operations.

Agents need a similar management boundary. Each agent has configuration that callers
reference, with permissions controlling who can configure or invoke it. The ownership
model must support these needs while keeping creation and everyday management
understandable.

Both options can reuse Baserow's application infrastructure, permission system, internal
tools and supported backend services. Sharing a management boundary does not by itself
authorize sharing integrations, determine execution identity or provide orchestration.
The `Agent` subject remains distinct from an agent.

This record decides the ownership model. Execution, orchestration and workspace
integrations are outside its scope. The
[delivery issue](https://github.com/baserow/baserow/issues/6259) defines release scope.

## Options considered

### 1. Agent Builder

An Agent Builder is a workspace application containing a list of independently
configured agents, following the database-and-tables model. Users create the Agent
Builder and then create agents within it. The Agent Builder provides a common management
boundary, while each agent has its own ID, configuration and role assignments.

This fits users who want to manage related agents together. Roles and shared settings
can be applied on the Agent Builder, with exceptions for individual agents where needed.
The Agent Builder is also a natural unit for lifecycle operations on related agents.
These benefits require a parent/child model, operations to manage the agents inside it,
permission-filtered navigation and lifecycle handling for the agents it contains.

### 2. Agent application

Each agent application is one agent and directly owns its configuration. Users create it
through the standard application flow, configure it and open it from its sidebar entry.
Callers reference its application ID.

This gives each agent independent roles and lifecycle operations through existing
application code. Related agents have separate sidebar entries and role assignments;
managing them together requires additional support.

| Aspect                        | Agent Builder (option 1)                             | Agent application (option 2)                   | Favours           |
| ----------------------------- | ---------------------------------------------------- | ---------------------------------------------- | ----------------- |
| First agent                   | Create the Agent Builder, then the agent             | Create the agent                               | Agent application |
| Many agents                   | One sidebar entry                                    | One sidebar entry each                         | Agent Builder     |
| Roles for related agents      | Set once on the Agent Builder                        | Set on each agent, or workspace-wide           | Agent Builder     |
| Roles for one agent           | Override per agent, a new scope                      | Existing application roles                     | Agent application |
| Duplicate, export, snapshot   | All related agents together; links between them kept | One agent; links between agents need remapping | Depends           |
| Build effort                  | Nested agent CRUD, scopes, navigation, lifecycle     | Existing application infrastructure            | Agent application |
| Grouping related agents later | Already available                                    | Migrate application IDs, roles and references  | Agent Builder     |

## Decision

Represent each agent as an agent application: a workspace application with application
type `agent`. Each agent application directly owns one agent's configuration and uses
application roles and lifecycle operations. Callers reference the application ID.
Configuration, invocation and private conversation/run visibility remain separate
permission concerns.

Per-agent roles need role-based access control (RBAC), available on the Advanced and
Enterprise plans. Without it, members get the same access to every agent, based on their
workspace role.

We expect users to start by wanting to build a single agent. Making that agent the
application gives them one thing to name, configure, open and manage. Independent roles
and lifecycle operations also match the agent as the unit that callers select. Existing
application operations support this model with less additional ownership and permission
machinery.

The Agent Builder is consistent with databases, Application Builders and Automations,
and offers useful shared administration and lifecycle operations. However, we do not yet
have established requirements for managing related agents together. We prefer the clear
benefits of a simple starting point over immediate structural complexity for possible
future needs. We accept that introducing an Agent Builder later may require more work.

## Consequences

- Each agent has a direct creation flow and independent roles and lifecycle operations.
  More agents also mean more sidebar entries, and administering related agents can
  involve repeated role assignments, resource-access configuration and settings changes.
- **Agents are referenced by application ID.** APIs, callers and exported references
  will depend on application IDs. A future change to the ownership model must preserve
  those references or provide migration and compatibility handling.
- **Permissions and configuration ownership become established boundaries.** Introducing
  an Agent Builder later would require rules for inherited roles, shared settings and
  resource access, including how to resolve conflicts while preserving effective access.
- **Lifecycle operations are per agent.** Coordinated duplication, installation,
  release, restoration or deletion of related agents will need dependency handling and
  additional lifecycle rules. Grouping agents in the sidebar alone would not provide
  those guarantees.
- **Snapshots are per agent.** Rolling back one agent restores only that agent, without
  touching the others. Rolling back related agents takes one restore each, and links
  between the restored agents still point to the originals. An Agent Builder would
  restore them together and keep those links. As with any Baserow application, a
  restore creates a new application, so callers keep referencing the original until
  pointed at the new ID. Restoring a database snapshot works the same way: automations
  keep referencing the original database.
- Collaboration can be designed through references between independent agent
  applications. That would still need authorization and policies for missing
  dependencies, duplication and deletion; this ownership decision does not prescribe an
  execution model.
- Workspace integrations may reduce repeated integration setup under either option.
  Shared agent settings, resource access and governance remain separate needs and are
  not solved by changing integration ownership alone.

Introducing an Agent Builder would become more costly once application IDs, caller
references, role assignments and lifecycle contracts are in use. We accept that
potential migration cost in exchange for simplicity now, while the need to manage
related agents together is uncertain.

## Revisit triggers

- Users repeatedly configure the same roles, resource access or settings across related
  agents and need those changes to propagate to all of them.
- Repeated integration setup remains costly after workspace integrations are available.
- Customers need clear management and access boundaries for related agents, similar to
  the boundaries provided by databases/tables, Application Builders/pages or
  Automations/workflows.
- Related agents regularly need to be installed, released, restored or deleted together.
