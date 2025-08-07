from django.core.management.base import BaseCommand

from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler


class Command(BaseCommand):
    help = "Generate and display a node graph starting from a given node ID"

    def add_arguments(self, parser):
        parser.add_argument(
            "worfklow_id", type=int, help="ID of the workflow to display"
        )

    def handle(self, *args, **options):
        worfklow_id = options["worfklow_id"]

        workflow = AutomationWorkflowHandler().get_workflow(worfklow_id)
        trigger = workflow.get_trigger()

        graph_visualization = self.generate_node_graph(trigger)
        self.stdout.write(graph_visualization)

    def generate_node_graph(self, start_node, visited=None, depth=0):
        node_type = start_node.get_type().type
        edges = start_node.service.get_type().get_edges(start_node.service.specific)

        if depth == 0:
            result = node_type
        else:
            result = node_type

        if not edges:
            return result

        # Process first edge (main flow)
        first_edge = edges[0]
        next_nodes = start_node.get_next_nodes(first_edge["uid"])
        if next_nodes:
            edge_label = f"({first_edge['label']})" if first_edge["label"] else ""
            result += f" ─{edge_label}→ "
            result += self.generate_node_graph(next_nodes[0], depth)

        # Process remaining edges (branches)
        for i, edge in enumerate(edges[1:], 1):
            next_nodes = start_node.get_next_nodes(edge["uid"])
            if next_nodes:
                is_last_edge = i == len(edges) - 1
                branch_symbol = "└" if is_last_edge else "├"
                edge_label = f"({edge['label']})" if edge["label"] else ""

                # Calculate indentation based on the full path length up to this point
                current_line_length = len(result.split("\n")[0])
                indent = " " * current_line_length

                result += f"\n{indent}{branch_symbol}─{edge_label}→ "

                # For continuation, use proper spacing
                continuation_char = " " if is_last_edge else "│"
                continuation_indent = (
                    indent + continuation_char + " " * (len(edge_label) + 4)
                )

                branch_result = self.generate_node_graph(next_nodes[0], depth + 1)
                # Replace newlines in branch result with proper indentation
                branch_lines = branch_result.split("\n")
                result += branch_lines[0]
                for line in branch_lines[1:]:
                    result += f"\n{continuation_indent}{line}"

        return result
