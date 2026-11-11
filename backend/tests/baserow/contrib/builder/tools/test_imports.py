import ast
from pathlib import Path

import baserow

SHARED_FOLDERS = (
    "contrib/builder/tools",
    "contrib/builder/mcp",
    "core/tools",
)
FORBIDDEN = ("pydantic_ai", "baserow_premium", "baserow_enterprise")


def _forbidden_imports(root: Path, path: Path) -> list[str]:
    package = ["baserow", *path.relative_to(root).parts[:-1]]
    found = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = package[: len(package) - (node.level - 1)] if node.level else []
            module = ".".join([*base, *([node.module] if node.module else [])])
            # ``from baserow_enterprise import assistant`` imports a submodule.
            modules = [module, *(f"{module}.{alias.name}" for alias in node.names)]
        else:
            continue
        for module in modules:
            if any(
                module == name or module.startswith(name + ".") for name in FORBIDDEN
            ):
                found.append(f"{path}:{node.lineno} imports {module}")
    return found


def test_shared_builder_code_imports_no_model_and_no_paid_edition():
    root = Path(baserow.__file__).parent
    assert sorted((root / "contrib/builder/tools").rglob("*.py"))

    problems = []
    for folder in SHARED_FOLDERS:
        for path in sorted((root / folder).rglob("*.py")):
            problems.extend(_forbidden_imports(root, path))

    assert problems == []
