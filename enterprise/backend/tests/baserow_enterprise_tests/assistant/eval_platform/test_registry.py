import pytest

from baserow_enterprise.assistant.evals import registry
from baserow_enterprise.assistant.evals.types import CheckResult, EvalCase


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    monkeypatch.setattr(registry, "_cases", {})
    monkeypatch.setattr(registry, "_scenarios", {})


def _noop_checks(case, scenario, output):
    return [CheckResult(name="noop", passed=True)]


def _make_case(case_id: str, dataset: str = "kuma-database") -> EvalCase:
    return EvalCase(
        id=case_id,
        dataset=dataset,
        prompt="do the thing",
        scenario="empty-workspace",
        checks=_noop_checks,
    )


class TestRegisterCase:
    def test_registering_duplicate_id_raises(self):
        registry.register_case(_make_case("database/dup-case"))

        with pytest.raises(ValueError, match="database/dup-case"):
            registry.register_case(_make_case("database/dup-case"))

    def test_get_case_returns_registered_case(self):
        case = _make_case("database/lookup-case")
        registry.register_case(case)

        assert registry.get_case("database/lookup-case") is case

    def test_get_unknown_case_raises_clear_error(self):
        with pytest.raises(KeyError, match="unknown/case"):
            registry.get_case("unknown/case")


class TestCasesByDataset:
    def test_groups_and_sorts(self):
        registry.register_case(_make_case("group/b-case", dataset="kuma-group-a"))
        registry.register_case(_make_case("group/a-case", dataset="kuma-group-a"))
        registry.register_case(_make_case("group/c-case", dataset="kuma-group-b"))

        grouped = registry.cases_by_dataset()

        assert [c.id for c in grouped["kuma-group-a"]] == [
            "group/a-case",
            "group/b-case",
        ]
        assert [c.id for c in grouped["kuma-group-b"]] == ["group/c-case"]

    def test_all_cases_sorted_by_id(self):
        registry.register_case(_make_case("sorted/b-case"))
        registry.register_case(_make_case("sorted/a-case"))

        assert [c.id for c in registry.all_cases()] == [
            "sorted/a-case",
            "sorted/b-case",
        ]


class TestScenarioRegistry:
    def test_register_and_get_scenario(self):
        @registry.register_scenario("dummy-scenario")
        def _build(fixtures):
            raise NotImplementedError

        assert registry.get_scenario("dummy-scenario") is _build

    def test_registering_duplicate_scenario_raises(self):
        registry.register_scenario("dup-scenario")(lambda fixtures: None)

        with pytest.raises(ValueError, match="dup-scenario"):
            registry.register_scenario("dup-scenario")(lambda fixtures: None)

    def test_get_unknown_scenario_raises_clear_error(self):
        with pytest.raises(KeyError, match="unknown-scenario"):
            registry.get_scenario("unknown-scenario")
