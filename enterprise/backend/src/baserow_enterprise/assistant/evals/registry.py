from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable

from baserow_enterprise.assistant.evals.types import EvalCase, ScenarioBuilder

_cases: dict[str, EvalCase] = {}
_scenarios: dict[str, ScenarioBuilder] = {}
_loaded = False


def register_case(case: EvalCase) -> EvalCase:
    if case.id in _cases:
        raise ValueError(f"Eval case '{case.id}' is already registered")
    _cases[case.id] = case
    return case


def register_scenario(
    name: str,
) -> Callable[[ScenarioBuilder], ScenarioBuilder]:
    def decorator(builder: ScenarioBuilder) -> ScenarioBuilder:
        if name in _scenarios:
            raise ValueError(f"Scenario '{name}' is already registered")
        _scenarios[name] = builder
        return builder

    return decorator


def get_case(case_id: str) -> EvalCase:
    try:
        return _cases[case_id]
    except KeyError:
        raise KeyError(f"Unknown eval case '{case_id}'") from None


def get_scenario(name: str) -> ScenarioBuilder:
    try:
        return _scenarios[name]
    except KeyError:
        raise KeyError(f"Unknown scenario '{name}'") from None


def cases_by_dataset() -> dict[str, list[EvalCase]]:
    grouped: dict[str, list[EvalCase]] = {}
    for case in sorted(_cases.values(), key=lambda c: c.id):
        grouped.setdefault(case.dataset, []).append(case)
    return grouped


def all_cases() -> list[EvalCase]:
    return sorted(_cases.values(), key=lambda c: c.id)


def load_all() -> None:
    """Import every ``evals.datasets`` submodule once, registering their cases."""

    global _loaded
    if _loaded:
        return

    from baserow_enterprise.assistant.evals import datasets

    for module_info in pkgutil.iter_modules(datasets.__path__):
        importlib.import_module(f"{datasets.__name__}.{module_info.name}")

    _loaded = True
