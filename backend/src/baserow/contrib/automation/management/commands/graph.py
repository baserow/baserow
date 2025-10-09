from django.core.management.base import BaseCommand

from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler


class Command(BaseCommand):
    help = "Generate and display a node graph starting from a workflow's trigger"

    def add_arguments(self, parser):
        parser.add_argument(
            "workflow_id", type=int, help="ID of the workflow to display"
        )
        parser.add_argument(
            "--max-depth",
            type=int,
            default=None,
            help="Limit traversal depth (0=root only, 1=children, etc.)",
        )

    def handle(self, *args, **options):
        workflow_id = options["workflow_id"]
        max_depth = options["max_depth"]

        workflow = AutomationWorkflowHandler().get_workflow(workflow_id)
        trigger = workflow.get_trigger()

        lines = self._build_tree(trigger, max_depth=max_depth)
        self.stdout.write("\n".join(lines))

    # ---------- Tree building ----------

    def _build_tree(self, start_node, max_depth=None):
        tee, last, vert, space = "├── ", "└── ", "│   ", "    "
        root_label = start_node.get_type().type
        lines = [root_label]

        visited = set()
        self._dfs(
            node=start_node,
            prefix="",
            parent_is_last=True,
            lines=lines,
            tee=tee,
            last=last,
            vert=vert,
            space=space,
            visited=visited,
            depth=0,
            max_depth=max_depth,
        )
        return lines

    def _dfs(
        self,
        node,
        prefix,
        parent_is_last,
        lines,
        tee,
        last,
        vert,
        space,
        visited,
        depth,
        max_depth,
    ):
        # Depth limiting
        if max_depth is not None and depth >= max_depth:
            return

        if node.id in visited:
            # Show cycle and bail from this branch
            lines.append(f"{prefix}{last if parent_is_last else tee}(cycle)")
            return
        visited.add(node.id)

        # Gather all (edge, child) pairs
        edges = node.service.get_type().get_edges(node.service.specific)
        children = []
        for edge in edges:
            next_nodes = node.get_next_nodes(edge["uid"])
            if not next_nodes:
                continue
            for idx, child in enumerate(next_nodes):
                # If multiple children for same edge, annotate with #n
                label = edge["label"]
                children.append((label, child))

        # Walk the children with correct branch characters/prefix handling
        total = len(children)
        for i, (edge_label, child) in enumerate(children):
            is_last = i == total - 1
            branch = last if is_last else tee

            # One line for the edge + child label
            child_label = child.get_type().type
            if edge_label:
                line = f"{prefix}{branch}{edge_label} {child_label}"
            else:
                line = f"{prefix}{branch}{child_label}"
            lines.append(line)

            # Recurse into child with extended prefix
            child_prefix = prefix + (space if is_last else vert)
            self._dfs(
                node=child,
                prefix=child_prefix,
                parent_is_last=is_last,
                lines=lines,
                tee=tee,
                last=last,
                vert=vert,
                space=space,
                visited=visited,
                depth=depth + 1,
                max_depth=max_depth,
            )

        # Remove from visited as we backtrack (allows other paths to revisit legitimately)
        if node.id is not None and node.id in visited:
            visited.remove(node.id)
