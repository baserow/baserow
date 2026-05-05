---
name: core-graph
description: Use this skill when working on code involving Element/Page relationships in the Application Builder (contrib/builder) or AutomationNode/AutomationWorkflow relationships in the Automation Builder (contrib/automation). This includes bugs, new features, or refactoring involving node/element placement, element place_in_container, container elements, parent/child/sibling traversal, node edges, or next/previous navigation between points.
---

# Core graph

## What this is

The `core/graph` package contains a reusable graph which the Application and Automation Builder (in `contrib/builder` and `contrib/automation` respectively) rely on.

In the Application Builder, it is used to manage and traverse the relationship between `Element`.

In the Automation Builder, it is used to manage and traverse the relationship between `AutomationNode`.

## Core abstractions

- A graph is made up of **points**. This term is deliberately abstract — what a point represents varies between modules (see "How X Builder uses it" sections below).
- An **edge** connects points. Edge semantics also vary per module (see "How X Builder uses it" sections below).
- Points can be **traversed** to determine the "next", "previous", and "parent" points.
- The graph itself is a **JSON object**.
- The graph is stored on a Django **container model** that implements `GraphModelMixin`. Individual **point models** implement `GraphPointMixin`, which provides helpers for traversal, parent access, edge labels, etc.
- An empty string (`""`) consistently represents the default/fallback edge throughout the system — in edge dictionaries, in `children` maps, and in migration from legacy formats.

## Design principles

- **`core/graph` must remain module-agnostic.** No references to `Element`, `AutomationNode`, or any other module-specific concept should appear in `core/graph` code.
- **Push module-specific logic out.** If a feature in the Application or Automation Builder has requirements specific to that module, the reusable parts belong in `core/graph` and the module-specific code belongs in the consuming module.

## Key files

- `src/baserow/core/graph/` - the directory containing the graph system.
- `tests/baserow/core/graph/` - the directory for all backend graph system tests.
- `src/baserow/core/graph/handler.py` — contains the `BaseGraphHandler`
- `src/baserow/core/graph/models.py` — contains the two Django `Model` mixins.


## How Application Builder uses it

- The container model is `Page`; the point model is `Element`.
- Most points won't have an edge, it'll just be a blank string. If, however, the element's parent implements `ContainerElementTypeMixin`, then its edge is the element's `place_in_container`. For example:
    - `element1` is a `ColumnElement` (so its type is `ColumnElementType`, which implements `ContainerElementTypeMixin`). This column has `column_amount=3`.
    - `element2` is a `HeadingElement`. We want it in the second column. We will make its parent `element1`, and set its `place_in_container` to "1".
- At the moment, there is at most one edge between elements, and it's always a string (whether blank, or a numeric `place_in_container`).

## How Automation Builder uses it

- The container model is `AutomationWorkflow`; the point model is `AutomationNode`.
- Points in automation builder can have one or more edges. They can be found by fetching the service, and calling `get_edges`. For example:
    - `node1` is an `AutomationNode`.
    - `service1 = node1.service.specific.get_type()` gives me `node1`'s service type.
    - `service1.get_edges()` returns a dictionary defining the edges between my nodes.
    - Most node services `get_edges` calls will return `{"": {"label": ""}}`. This represents a straight traversal without an edge name — the outer dictionary key of `""` is the default-edge convention (see Core abstractions). The `label` in the inner dictionary is a user-configured label they can see in the UI.
    - The `CoreRouterServiceType` however will return a UUID for the outer dictionary key, for each edge the user has configured, and a default edge (which is the fallback). E.g.
        - `{"condition1Uuid": {"label": "Condition1"}, "condition2Uuid": {"label": "Condition2"}, "": {"label": "Default fallback"}}`

## Common operations

- Given a container model instance, call `.get_graph()` to get the graph handler. This is the standard entry point for inserting, removing, or moving points. Example: `page.get_graph()` in the Application Builder, `workflow.get_graph()` in the Automation Builder.
- Given a point model instance, the `GraphPointMixin` methods provide traversal helpers (next/previous/parent), edge label access, and related operations. Prefer these over hand-rolling traversal logic.

## Common pitfalls

- In the graph, `children` does not contain *all* child points, only the "first" child of the container. To find *all* children, you must choose that first child point, and then keep traversing next until no points remain.
- It is possible to run into a "legacy" `children` that looks like this: `{"children": [7]}`. The `BaseGraphHandler` will support this, and migrate it to the new format: `{"children": {"": [7]}}` (the `""` key follows the default-edge convention described in Core abstractions).

## Testing

- Ensure any handler modifications are tested in its test file, `test_graph_handler.py`.
- Ensure any model mixin modifications are tested in their test file, `test_graph_models.py`.
- Test fixtures and configuration can be found in the test directory's `fixtures.py` and `conftest.py`.
