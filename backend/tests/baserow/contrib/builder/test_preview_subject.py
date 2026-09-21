import pytest

from baserow.contrib.builder.preview import BuilderPreviewActor
from baserow.contrib.builder.preview.subjects import BuilderPreviewActorSubjectType


@pytest.mark.django_db
@pytest.mark.parametrize("include_trash", [False, True])
def test_builder_preview_actor_workspace_check_accepts_include_trash(
    data_fixture, include_trash
):
    workspace = data_fixture.create_workspace()
    actor = BuilderPreviewActor(
        builder_id=1,
        workspace_id=workspace.id,
        grant_id=2,
        issued_by_user_id=3,
    )

    assert BuilderPreviewActorSubjectType().is_in_workspace(
        actor, workspace, include_trash=include_trash
    )
