import ast
from typing import Iterator, Tuple, Any


class BaserowPsycopgChecker:
    name = "flake8-baserow-psycopg"
    version = "0.1.0"

    def __init__(self, tree: ast.AST, filename: str):
        self.tree = tree
        self.filename = filename

    def run(self) -> Iterator[Tuple[int, int, str, Any]]:
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ("psycopg", "psycopg2"):
                        yield (
                            node.lineno,
                            node.col_offset,
                            "BPG001 Import psycopg/psycopg2 from baserow.core.psycopg instead",
                            type(self),
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module in ("psycopg", "psycopg2"):
                    yield (
                        node.lineno,
                        node.col_offset,
                        "BPG001 Import psycopg/psycopg2 from baserow.core.psycopg instead",
                        type(self),
                    )
