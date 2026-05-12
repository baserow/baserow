import json
from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.amber import AmberSnapshotExtension
from syrupy.location import PyTestLocation

from baserow.core.handler import CoreHandler
from baserow.core.models import Template
from baserow.core.registries import application_type_registry

TEMPLATES_DIR = Path(__file__).parents[4] / "templates"

_template_slugs = sorted(
    p.stem
    for p in TEMPLATES_DIR.glob("*.json")
    if json.loads(p.read_text()).get("baserow_template_version")
)


class PerTemplateSnapshotExtension(AmberSnapshotExtension):
    """
    An extension which changes the default snapshot behavior (one monolithic snapshot)
    in favor of writing one .ambr file per template slug under __snapshots__/templates/.
    """

    @classmethod
    def dirname(cls, *, test_location: "PyTestLocation", **kwargs) -> str:
        return str(Path(test_location.filepath).parent / "__snapshots__")

    @classmethod
    def get_file_basename(
        cls, *, test_location: "PyTestLocation", index: int, **kwargs
    ) -> str:
        # node id: "...::test_template_snapshot[slug-name]" → "slug-name"
        node_id = test_location.nodeid
        if "[" in node_id:
            return node_id.split("[", 1)[1].rstrip("]")
        return super().get_file_basename(
            test_location=test_location, index=index, **kwargs
        )


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    return snapshot.use_extension(PerTemplateSnapshotExtension)


@pytest.mark.django_db
@pytest.mark.once_per_day_in_ci
@pytest.mark.parametrize("slug", _template_slugs)
def test_template_snapshot(slug: str, snapshot: SnapshotAssertion) -> None:
    """
    Imports a single template and asserts the application structure matches the
    stored snapshot. Run with `--snapshot-update` to (re)generate snapshots.
    """

    CoreHandler().sync_templates(pattern=slug)

    template = Template.objects.get(slug=slug)
    applications = template.workspace.application_set.order_by("name")

    result = {}
    for app in applications:
        app_type = application_type_registry.get_by_model(app.specific_class)
        serialized = app_type.serialize_for_regression_testing(app.specific)
        if serialized is not None:
            result[app_type.type] = serialized

    assert result == snapshot
