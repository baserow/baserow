import pytest

from baserow.contrib.builder.models import Builder
from baserow.core.exceptions import PermissionException
from baserow.core.service import CoreService
from baserow.core.tools.errors import ToolInputError
from baserow_enterprise.assistant.tools.builder.tools import set_theme
from baserow_enterprise_tests.assistant.utils import make_test_ctx


@pytest.mark.django_db
def test_kuma_reports_a_hidden_builder_as_not_found_like_mcp(builder_ctx, monkeypatch):
    builder = Builder.objects.create(
        workspace=builder_ctx["workspace"], name="Portal", order=1
    )

    def deny(*args, **kwargs):
        raise PermissionException()

    monkeypatch.setattr(CoreService, "get_application", deny)
    kuma_ctx = make_test_ctx(builder_ctx["user"], builder_ctx["workspace"])

    with pytest.raises(ToolInputError, match=f"Application with ID {builder.id} not"):
        set_theme(kuma_ctx, builder.id, "baserow", "t")
