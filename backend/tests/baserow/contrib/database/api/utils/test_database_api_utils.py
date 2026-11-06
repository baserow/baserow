from urllib.parse import quote

from django.urls import reverse

import pytest
from rest_framework.request import Request

from baserow.contrib.database.api.utils import (
    LinkedTargetField,
    LinkRowJoin,
    extract_link_row_joins_from_request,
)
from baserow.contrib.database.fields.exceptions import (
    FieldDoesNotExist,
    IncompatibleField,
)
from baserow.contrib.database.fields.field_types import TextFieldType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field


def api_request(user, request):
    api_request = Request(request)
    api_request.user = user
    return api_request


@pytest.mark.django_db
def test_extract_link_row_joins_from_request(data_fixture, rf):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    linked_table_text_field = data_fixture.create_text_field(
        table=linked_table, order=0, name="Text field"
    )
    link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table
    )
    valid_field_reference = (
        f"?field_{link_row_field.id}__join=field_{linked_table_text_field.id}"
    )
    request = api_request(
        user,
        rf.get(
            reverse("api:database:rows:list", kwargs={"table_id": table.id})
            + valid_field_reference
        ),
    )
    link_row_fields = (
        Field.objects.filter(table=table)
        .select_related("content_type")
        .filter(content_type__model="linkrowfield")
    )

    result = extract_link_row_joins_from_request(request, link_row_fields)

    assert result == [
        LinkRowJoin(
            link_row_field_id=link_row_field.id,
            link_row_field_ref=f"field_{link_row_field.id}",
            target_fields=[
                LinkedTargetField(
                    field_id=linked_table_text_field.id,
                    field_ref=f"field_{linked_table_text_field.id}",
                    field_serializer=TextFieldType().get_response_serializer_field(
                        linked_table_text_field
                    ),
                )
            ],
        )
    ]


@pytest.mark.django_db
def test_extract_link_row_joins_from_request_user_field_names(data_fixture, rf):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    linked_table_text_field = data_fixture.create_text_field(
        table=linked_table, order=0, name="Text field"
    )
    link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table
    )
    valid_field_reference = (
        f"?{quote(link_row_field.name)}__join={quote(linked_table_text_field.name)}"
    )
    request = api_request(
        user,
        rf.get(
            reverse("api:database:rows:list", kwargs={"table_id": table.id})
            + valid_field_reference
            + "&user_field_names"
        ),
    )
    link_row_fields = (
        Field.objects.filter(table=table)
        .select_related("content_type")
        .filter(content_type__model="linkrowfield")
    )

    result = extract_link_row_joins_from_request(
        request, link_row_fields, user_field_names=True
    )

    assert result == [
        LinkRowJoin(
            link_row_field_id=link_row_field.id,
            link_row_field_ref=link_row_field.name,
            target_fields=[
                LinkedTargetField(
                    field_id=linked_table_text_field.id,
                    field_ref=linked_table_text_field.name,
                    field_serializer=TextFieldType().get_response_serializer_field(
                        linked_table_text_field,
                        source=f"field_{linked_table_text_field.id}",
                    ),
                )
            ],
        )
    ]


@pytest.mark.django_db
def test_extract_link_row_joins_from_request_multiple_lookups(data_fixture, rf):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    linked_table_text_field = data_fixture.create_text_field(
        table=linked_table, order=0, name="Text field"
    )
    linked_table_text_field_2 = data_fixture.create_text_field(
        table=linked_table, order=0, name="Text field 2"
    )
    linked_table_2 = data_fixture.create_database_table(user=user)
    linked_table_2_text_field = data_fixture.create_text_field(
        table=linked_table_2, order=0, name="Table 2 Text field"
    )
    link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table
    )
    link_row_field_2 = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table_2
    )
    join_params = (
        f"?field_{link_row_field.id}__join=field_{linked_table_text_field.id}"
        f",field_{linked_table_text_field_2.id}"
        f"&field_{link_row_field_2.id}__join=field_{linked_table_2_text_field.id}"
    )
    request = api_request(
        user,
        rf.get(
            reverse("api:database:rows:list", kwargs={"table_id": table.id})
            + join_params
        ),
    )
    link_row_fields = (
        Field.objects.filter(table=table)
        .select_related("content_type")
        .filter(content_type__model="linkrowfield")
    )

    result = extract_link_row_joins_from_request(request, link_row_fields)

    assert result == [
        LinkRowJoin(
            link_row_field_id=link_row_field.id,
            link_row_field_ref=f"field_{link_row_field.id}",
            target_fields=[
                LinkedTargetField(
                    field_id=linked_table_text_field.id,
                    field_ref=f"field_{linked_table_text_field.id}",
                    field_serializer=TextFieldType().get_response_serializer_field(
                        linked_table_text_field
                    ),
                ),
                LinkedTargetField(
                    field_id=linked_table_text_field_2.id,
                    field_ref=f"field_{linked_table_text_field_2.id}",
                    field_serializer=TextFieldType().get_response_serializer_field(
                        linked_table_text_field_2
                    ),
                ),
            ],
        ),
        LinkRowJoin(
            link_row_field_id=link_row_field_2.id,
            link_row_field_ref=f"field_{link_row_field_2.id}",
            target_fields=[
                LinkedTargetField(
                    field_id=linked_table_2_text_field.id,
                    field_ref=f"field_{linked_table_2_text_field.id}",
                    field_serializer=TextFieldType().get_response_serializer_field(
                        linked_table_2_text_field
                    ),
                )
            ],
        ),
    ]


@pytest.mark.django_db
def test_extract_link_row_joins_from_request_invalid_reference(data_fixture, rf):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    linked_table_text_field = data_fixture.create_text_field(
        table=linked_table, order=0, name="Text"
    )
    field_outside_linked_table = data_fixture.create_text_field(
        table=table, order=1, name="Text field outside target table"
    )
    link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table
    )
    link_row_fields = (
        Field.objects.filter(table=table)
        .select_related("content_type")
        .filter(content_type__model="linkrowfield")
    )
    linked_table_link_row_field = data_fixture.create_link_row_field(
        table=linked_table, link_row_table=table
    )

    # link row field doesn't exist
    invalid_field_reference = "?field_9999__join=field_99999"
    request = api_request(
        user,
        rf.get(
            reverse("api:database:rows:list", kwargs={"table_id": table.id})
            + invalid_field_reference
        ),
    )
    with pytest.raises(FieldDoesNotExist):
        extract_link_row_joins_from_request(request, link_row_fields)

    # link row field is not a link row field
    not_lookup_field_reference = (
        f"?field_{field_outside_linked_table.id}__join=field_99999"
    )
    request = api_request(
        user,
        rf.get(
            reverse("api:database:rows:list", kwargs={"table_id": table.id})
            + not_lookup_field_reference
        ),
    )
    with pytest.raises(FieldDoesNotExist):
        extract_link_row_joins_from_request(request, link_row_fields)

    # target field doesn't exist
    invalid_linked_field_reference = f"?field_{link_row_field.id}__join=field_99999"
    request = api_request(
        user,
        rf.get(
            reverse("api:database:rows:list", kwargs={"table_id": table.id})
            + invalid_linked_field_reference
        ),
    )
    with pytest.raises(FieldDoesNotExist):
        extract_link_row_joins_from_request(request, link_row_fields)

    # target field is not in the looked up table
    field_outside_linked_table_reference = (
        f"?field_{link_row_field.id}__join=field_{field_outside_linked_table.id}"
    )
    request = api_request(
        user,
        rf.get(
            reverse("api:database:rows:list", kwargs={"table_id": table.id})
            + field_outside_linked_table_reference
        ),
    )
    with pytest.raises(FieldDoesNotExist):
        extract_link_row_joins_from_request(request, link_row_fields)

    # target field cannot be a link to table field
    linked_table_link_row_field_reference = (
        f"?field_{link_row_field.id}__join=field_{linked_table_link_row_field.id}"
    )
    request = api_request(
        user,
        rf.get(
            reverse("api:database:rows:list", kwargs={"table_id": table.id})
            + linked_table_link_row_field_reference
        ),
    )
    with pytest.raises(IncompatibleField):
        extract_link_row_joins_from_request(request, link_row_fields)

    # trashed field
    FieldHandler().delete_field(user, linked_table_text_field)
    trashed_field_linked_table_reference = (
        f"?field_{link_row_field.id}__join=field_{linked_table_text_field.id}"
    )
    request = api_request(
        user,
        rf.get(
            reverse("api:database:rows:list", kwargs={"table_id": table.id})
            + trashed_field_linked_table_reference
        ),
    )
    with pytest.raises(FieldDoesNotExist):
        extract_link_row_joins_from_request(request, link_row_fields)


@pytest.mark.django_db
def test_extract_link_row_joins_from_request_invalid_reference_user_field_names(
    data_fixture, rf
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    linked_table_text_field = data_fixture.create_text_field(
        table=linked_table, order=0, name="Text"
    )
    field_outside_linked_table = data_fixture.create_text_field(
        table=table, order=1, name="Text field outside target table"
    )
    link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table, name="LinkField"
    )
    link_row_fields = (
        Field.objects.filter(table=table)
        .select_related("content_type")
        .filter(content_type__model="linkrowfield")
    )
    linked_table_link_row_field = data_fixture.create_link_row_field(
        table=linked_table, link_row_table=table
    )

    # link row field doesn't exist
    invalid_field_reference = (
        f"?DoesNotExist__join={quote(linked_table_text_field.name)}"
    )
    request = api_request(
        user,
        rf.get(
            reverse("api:database:rows:list", kwargs={"table_id": table.id})
            + invalid_field_reference
            + "&user_field_names"
        ),
    )
    with pytest.raises(FieldDoesNotExist):
        extract_link_row_joins_from_request(
            request, link_row_fields, user_field_names=True
        )

    # link row field is not a link row field
    not_lookup_field_reference = f"?{quote(field_outside_linked_table.name)}__join={quote(linked_table_text_field.name)}"
    request = api_request(
        user,
        rf.get(
            reverse("api:database:rows:list", kwargs={"table_id": table.id})
            + not_lookup_field_reference
            + "&user_field_names"
        ),
    )
    with pytest.raises(FieldDoesNotExist):
        extract_link_row_joins_from_request(
            request, link_row_fields, user_field_names=True
        )

    # target field doesn't exist
    invalid_linked_field_reference = f"?{quote(link_row_field.name)}__join=DoesNotExist"
    request = api_request(
        user,
        rf.get(
            reverse("api:database:rows:list", kwargs={"table_id": table.id})
            + invalid_linked_field_reference
            + "&user_field_names"
        ),
    )
    with pytest.raises(FieldDoesNotExist):
        extract_link_row_joins_from_request(
            request, link_row_fields, user_field_names=True
        )

    # target field is not in the looked up table
    field_outside_linked_table_reference = (
        f"?{quote(link_row_field.name)}__join={quote(field_outside_linked_table.name)}"
    )
    request = api_request(
        user,
        rf.get(
            reverse("api:database:rows:list", kwargs={"table_id": table.id})
            + field_outside_linked_table_reference
            + "&user_field_names"
        ),
    )
    with pytest.raises(FieldDoesNotExist):
        extract_link_row_joins_from_request(
            request, link_row_fields, user_field_names=True
        )

    # target field cannot be a link to table field
    linked_table_link_row_field_reference = (
        f"?{quote(link_row_field.name)}__join={quote(linked_table_link_row_field.name)}"
    )
    request = api_request(
        user,
        rf.get(
            reverse("api:database:rows:list", kwargs={"table_id": table.id})
            + linked_table_link_row_field_reference
            + "&user_field_names"
        ),
    )
    with pytest.raises(IncompatibleField):
        extract_link_row_joins_from_request(
            request, link_row_fields, user_field_names=True
        )

    # trashed field
    FieldHandler().delete_field(user, linked_table_text_field)
    trashed_field_linked_table_reference = (
        f"?{quote(link_row_field.name)}__join={quote(linked_table_text_field.name)}"
    )
    request = api_request(
        user,
        rf.get(
            reverse("api:database:rows:list", kwargs={"table_id": table.id})
            + trashed_field_linked_table_reference
            + "&user_field_names"
        ),
    )
    with pytest.raises(FieldDoesNotExist):
        extract_link_row_joins_from_request(
            request, link_row_fields, user_field_names=True
        )
