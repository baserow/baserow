import pytest

from baserow.contrib.builder.search_types import BuilderSearchType
from baserow.core.search.data_types import SearchContext


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_builder_search_type_basic_functionality(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(
        workspace=workspace, name="Test Builder"
    )

    search_type = BuilderSearchType()

    queryset = search_type.get_base_queryset(user, workspace)
    assert builder in queryset

    search_context = SearchContext(query="Test", limit=10, offset=0)
    search_results = search_type.get_search_queryset(user, workspace, search_context)
    assert builder in search_results

    search_result = search_type.serialize_result(builder, user, workspace)
    assert search_result.id == builder.id
    assert search_result.title == "Test Builder"
    assert search_result.type == "builder"
