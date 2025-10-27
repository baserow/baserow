import ast
from typing import Iterator, Tuple, Any


class BaserowAIImportsChecker:
    """
    Flake8 plugin to ensure dspy and litellm are only imported locally within
    functions/methods, not at module level.
    """

    name = "flake8-baserow-ai-imports"
    version = "0.1.0"

    def __init__(self, tree: ast.AST, filename: str):
        self.tree = tree
        self.filename = filename

    def run(self) -> Iterator[Tuple[int, int, str, Any]]:
        """Check for global imports of dspy and litellm."""
        for node in ast.walk(self.tree):
            # Check if this is a module-level import (not inside a function/method)
            if self._is_global_import(node):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if self._is_ai_module(alias.name):
                            yield (
                                node.lineno,
                                node.col_offset,
                                f"BAI001 {alias.name} must be imported locally within functions/methods, not globally",
                                type(self),
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module and self._is_ai_module(node.module):
                        yield (
                            node.lineno,
                            node.col_offset,
                            f"BAI001 {node.module} must be imported locally within functions/methods, not globally",
                            type(self),
                        )

    def _is_ai_module(self, module_name: str) -> bool:
        """Check if the module is dspy or litellm (including submodules)."""
        if not module_name:
            return False
        return (
            module_name == "dspy"
            or module_name.startswith("dspy.")
            or module_name == "litellm"
            or module_name.startswith("litellm.")
        )

    def _is_global_import(self, node: ast.AST) -> bool:
        """
        Check if an import node is at global scope.
        Returns True if the import is not nested inside a function or method.
        """
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            return False

        # Walk up the AST to find if this import is inside a function/method
        # We need to check the parent nodes, but ast.walk doesn't provide parent info
        # So we'll traverse the tree differently
        return self._check_node_is_global(self.tree, node)

    def _check_node_is_global(
        self, root: ast.AST, target: ast.AST, in_function: bool = False
    ) -> bool:
        """
        Recursively check if target node is at global scope.
        Returns True if the target is found at global scope (not in a function).
        """
        if root is target:
            return not in_function

        # Check if we're entering a function/method
        new_in_function = in_function or isinstance(
            root, (ast.FunctionDef, ast.AsyncFunctionDef)
        )

        # Recursively check all child nodes
        for child in ast.iter_child_nodes(root):
            result = self._check_node_is_global(child, target, new_in_function)
            if result is not None:
                return result

        return None
