"""
Guards the xdist worker-allocation policy used by the eval matrix.

Parallelism is spread across providers first, then models, then within a model.
If this breaks, several workers hit one provider at once and the resulting 429s
are indistinguishable from a model-quality regression in the scored comparison.
"""

import pytest

from . import conftest as eval_conftest
from .conftest import _group_name, _provider_of, _shards_per_model

# Four models on three providers: hetzner carries two.
MODELS = [
    "groq:openai/gpt-oss-120b",
    "hetzner:deepseek-v4-flash",
    "hetzner:glm5.2",
    "openai:gpt-5.6-luna",
]


def groups_for(models: list[str], workers: int, per_model: int = 6) -> dict[str, set]:
    """Return {model: set of group names} for *per_model* items of each model."""

    shards = _shards_per_model(models, workers)
    return {m: {_group_name(m, i, shards) for i in range(per_model)} for m in models}


@pytest.mark.parametrize(
    "model,expected",
    [
        ("groq:openai/gpt-oss-120b", "groq"),
        ("hetzner:deepseek-v4-flash", "hetzner"),
        ("infercom:vendor/some-model", "infercom"),
        ("gpt-4o", "openai"),
    ],
)
def test_provider_of(model, expected):
    assert _provider_of(model) == expected


def test_workers_at_or_below_provider_count_group_by_provider():
    # 3 workers, 3 providers -> one worker per provider, hetzner's two models share.
    groups = groups_for(MODELS, workers=3)

    assert groups["hetzner:deepseek-v4-flash"] == {"hetzner"}
    assert groups["hetzner:glm5.2"] == {"hetzner"}
    assert groups["groq:openai/gpt-oss-120b"] == {"groq"}
    assert len(set().union(*groups.values())) == 3


def test_fewer_workers_than_providers_still_groups_by_provider():
    groups = groups_for(MODELS, workers=2)

    assert len(set().union(*groups.values())) == 3


def test_workers_matching_model_count_give_one_worker_per_model():
    # 4 workers, 4 models -> hetzner's two models split onto their own workers.
    groups = groups_for(MODELS, workers=4)

    assert groups["hetzner:deepseek-v4-flash"] == {"hetzner:deepseek-v4-flash"}
    assert groups["hetzner:glm5.2"] == {"hetzner:glm5.2"}
    assert len(set().union(*groups.values())) == 4


def test_one_extra_worker_doubles_up_a_single_model():
    # 5 workers, 4 models -> exactly one model gets a second worker.
    groups = groups_for(MODELS, workers=5)

    sizes = sorted(len(g) for g in groups.values())
    assert sizes == [1, 1, 1, 2]
    assert len(set().union(*groups.values())) == 5


def test_double_the_models_gives_every_model_two_workers():
    groups = groups_for(MODELS, workers=8)

    assert all(len(g) == 2 for g in groups.values())
    assert len(set().union(*groups.values())) == 8


@pytest.mark.parametrize(
    "workers,expected_groups",
    # Below the provider count the layout stays at one group per provider; xdist
    # runs the surplus groups sequentially, so per-provider concurrency is still 1.
    [(1, 3), (2, 3), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (12, 12)],
)
def test_group_count_follows_the_waterfall(workers, expected_groups):
    groups = groups_for(MODELS, workers=workers, per_model=12)

    assert len(set().union(*groups.values())) == expected_groups


@pytest.mark.parametrize("workers", [1, 2, 3])
def test_scarce_workers_never_split_a_provider(workers):
    groups = groups_for(MODELS, workers=workers)

    per_provider: dict[str, set] = {}
    for model, names in groups.items():
        per_provider.setdefault(_provider_of(model), set()).update(names)

    assert all(len(names) == 1 for names in per_provider.values())


def test_single_provider_still_spreads_across_its_models():
    models = ["hetzner:a", "hetzner:b", "hetzner:c"]

    assert len(set().union(*groups_for(models, workers=1).values())) == 1
    assert len(set().union(*groups_for(models, workers=3).values())) == 3


class _StubConfig:
    def __init__(
        self, numprocesses, dist: str = "load", workercount: int | None = None
    ):
        self.option = type("opt", (), {"numprocesses": numprocesses, "dist": dist})()
        if workercount is not None:
            self.workerinput = {"workercount": workercount}


class _StubItem:
    def __init__(self, model: str | None):
        self.callspec = (
            type("cs", (), {"params": {"eval_model": model}})() if model else None
        )
        self.markers: list = []

    def add_marker(self, marker):
        self.markers.append(marker)

    @property
    def groups(self) -> list[str]:
        return [m.kwargs["name"] for m in self.markers if m.name == "xdist_group"]


def _items(models: list[str], per_model: int) -> list[_StubItem]:
    return [_StubItem(m) for m in models for _ in range(per_model)]


def test_items_are_tagged_at_collection_time():
    items = _items(MODELS, per_model=3)

    eval_conftest._assign_xdist_groups(_StubConfig(numprocesses=4), items)

    assert all(len(i.groups) == 1 for i in items)
    assert {i.groups[0] for i in items} == set(MODELS)


def test_a_model_split_across_workers_uses_distinct_groups():
    items = _items(MODELS, per_model=4)

    eval_conftest._assign_xdist_groups(_StubConfig(numprocesses=8), items)

    hetzner = [i for i in items if i.callspec.params["eval_model"] == "hetzner:glm5.2"]
    assert len({i.groups[0] for i in hetzner}) == 2


def test_serial_runs_are_left_ungrouped():
    items = _items(MODELS, per_model=2)

    eval_conftest._assign_xdist_groups(_StubConfig(numprocesses=None), items)

    assert all(i.groups == [] for i in items)


def test_non_eval_items_are_ignored():
    items = [_StubItem(None), _StubItem(None)]

    eval_conftest._assign_xdist_groups(_StubConfig(numprocesses=4), items)

    assert all(i.groups == [] for i in items)


def test_parallel_run_switches_to_loadgroup():
    config = _StubConfig(numprocesses=4)

    eval_conftest.pytest_configure(config)

    assert config.option.dist == "loadgroup"


def test_serial_run_keeps_default_scheduling():
    config = _StubConfig(numprocesses=None)

    eval_conftest.pytest_configure(config)

    assert config.option.dist == "load"


def test_explicit_dist_choice_is_respected():
    config = _StubConfig(numprocesses=4, dist="loadfile")

    eval_conftest.pytest_configure(config)

    assert config.option.dist == "loadfile"


def test_worker_sees_the_count_via_workerinput():
    # xdist workers are not launched with -n, so numprocesses is unset there.
    # They must still derive the same group layout as the controller.
    config = _StubConfig(numprocesses=None, workercount=4)

    assert eval_conftest._worker_count(config) == 4


def test_workers_group_items_identically_to_the_controller():
    controller_items = _items(MODELS, per_model=4)
    worker_items = _items(MODELS, per_model=4)

    eval_conftest._assign_xdist_groups(_StubConfig(numprocesses=8), controller_items)
    eval_conftest._assign_xdist_groups(
        _StubConfig(numprocesses=None, workercount=8), worker_items
    )

    assert [i.groups for i in controller_items] == [i.groups for i in worker_items]


def test_worker_without_workerinput_falls_back_to_serial():
    config = _StubConfig(numprocesses=None)

    assert eval_conftest._worker_count(config) == 1
