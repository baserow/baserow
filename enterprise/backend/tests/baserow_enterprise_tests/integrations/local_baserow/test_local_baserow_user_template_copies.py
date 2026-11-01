from django.contrib.auth.hashers import make_password

import pytest
from rest_framework.exceptions import AuthenticationFailed

from baserow.contrib.builder.models import Builder
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.jobs.constants import JOB_FINISHED
from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowPasswordAppAuthProvider,
    LocalBaserowUserSource,
)
from tests.baserow.core.user_templates.utils import install, start_job

pytestmark = [
    pytest.mark.import_export_workspace,
    pytest.mark.django_db(transaction=True),
    pytest.mark.usefixtures("use_tmp_media_root", "enable_enterprise", "synced_roles"),
]

EMAIL = "test@baserow.io"
PASSWORD = "source secret"


def authenticate(user_source):
    return user_source.get_type().authenticate(
        user_source, email=EMAIL, password=PASSWORD
    )


def assert_app_users_have_no_password(workspace):
    """
    Checks that the app's password provider still points at the copied password
    field and that no app user has a password in the copy. Returns the copied
    user source.
    """

    user_source = LocalBaserowUserSource.objects.get(
        application__in=Builder.objects.filter(workspace=workspace)
    )
    auth_provider = LocalBaserowPasswordAppAuthProvider.objects.get(
        user_source=user_source
    )
    password_field = user_source.table.field_set.get(name="Password")
    assert auth_provider.password_field_id == password_field.id
    assert list(
        user_source.table.get_model().objects.values_list(
            password_field.db_column, flat=True
        )
    ) == [None]
    return user_source


def test_app_users_have_no_password_in_user_template_copies(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table, (email_field, name_field, password_field), _ = data_fixture.build_table(
        user=user,
        database=database,
        columns=[("Email", "text"), ("Name", "text"), ("Password", "password")],
        rows=[[EMAIL, "Test", make_password(PASSWORD)]],
    )
    user_source = data_fixture.create_user_source(
        LocalBaserowUserSource,
        application=builder,
        integration=data_fixture.create_local_baserow_integration(
            application=builder, user=user
        ),
        table=table,
        email_field=email_field,
        name_field=name_field,
    )
    data_fixture.create_app_auth_provider(
        LocalBaserowPasswordAppAuthProvider,
        user_source=user_source,
        password_field=password_field,
    )
    assert authenticate(user_source).email == EMAIL

    # The template's integration has no authorized user, so its app users can't
    # log in at all; the empty password cell is what is checked there.
    template = start_job(user, workspace, [database, builder]).template
    assert_app_users_have_no_password(template.workspace)

    target = data_fixture.create_workspace(user=user)
    job = install(user, target, template)
    assert job.state == JOB_FINISHED
    installed_user_source = assert_app_users_have_no_password(target)
    with pytest.raises(AuthenticationFailed):
        authenticate(installed_user_source)

    # Once the installer sets a password again, the app user can log in.
    installed_table = installed_user_source.table
    installed_password_field = installed_table.field_set.get(name="Password")
    [installed_row] = installed_table.get_model().objects.all()
    RowHandler().update_row_by_id(
        user,
        installed_table,
        installed_row.id,
        {installed_password_field.db_column: make_password(PASSWORD)},
    )
    installed_user_source = LocalBaserowUserSource.objects.get(
        id=installed_user_source.id
    )
    assert authenticate(installed_user_source).email == EMAIL

    # The source app keeps its passwords.
    assert authenticate(user_source).email == EMAIL
