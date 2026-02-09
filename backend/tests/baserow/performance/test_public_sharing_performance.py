import pytest
from pyinstrument import Profiler

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
def test_creating_many_rows_in_public_filtered_views(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        columns=[("number", "number")], rows=[["0"]], user=user
    )

    num_public_views = 10
    views = []
    for i in range(num_public_views):
        views.append(data_fixture.create_grid_view(user=user, table=table, public=True))

    num_fields = 20
    for i in range(num_fields):
        last_field = FieldHandler().create_field(
            user=user,
            table=table,
            name=f"field{i}",
            type_name="text",
        )
        for view in views:
            data_fixture.create_view_filter(
                view=view, field=last_field, type="equal", value=i
            )
    handler = RowHandler()
    num_rows = 1000
    rows = []
    for i in range(num_rows):
        row = {}
        for j in range(num_fields):
            row[f"field_{j}"] = (i + j) % num_fields
        rows.append(row)
    model = table.get_model()
    profiler = Profiler()
    profiler.start()
    for i in range(num_rows):
        handler.create_row(user, table, rows[i], model=model)
    profiler.stop()
    print(profiler.output_text(unicode=True, color=True))


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
def test_updating_many_rows_in_public_filtered_views(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        columns=[("number", "number")], rows=[["0"]], user=user
    )

    num_public_views = 10
    num_fields = 100
    num_rows = 1000
    num_fields_to_filter = 3
    num_views_to_filter = 6
    num_row_updates_to_profile = 1

    views = []
    for i in range(num_public_views):
        views.append(data_fixture.create_grid_view(user=user, table=table, public=True))

    for i in range(num_fields):
        last_field = FieldHandler().create_field(
            user=user,
            table=table,
            name=f"field{i}",
            type_name="text",
        )
        if i < num_fields_to_filter:
            for view in views[:num_views_to_filter]:
                data_fixture.create_view_filter(
                    view=view, field=last_field, type="equal", value=i
                )
    handler = RowHandler()
    rows = []
    for i in range(num_rows):
        row = {}
        for j in range(num_fields):
            row[f"field_{j}"] = (i + j) % num_fields
        rows.append(row)
    model = table.get_model()
    for i in range(num_rows):
        rows[i] = handler.create_row(user, table, rows[i], model=model)
    profiler = Profiler()
    profiler.start()
    run_row_updates = 0
    for i in range(num_rows):
        for k in range(num_fields):
            handler.update_row_by_id(
                user, table, rows[i].id, {f"field_{k}": 0}, model=model
            )
            run_row_updates += 1
            if run_row_updates >= num_row_updates_to_profile:
                break
        if run_row_updates >= num_row_updates_to_profile:
            break
    profiler.stop()
    print(profiler.output_text(unicode=True, color=True))

    """
    Profiling result on 11/01/2021:
    - Dev: Nigel
    - Machine: 32gb RAM, Ubuntu 21.04, AMD 5900X
    - Variables:
        num_public_views = 10
        num_fields = 100
        num_rows = 1000
        num_fields_to_filter = 3
        num_views_to_filter = 6
        num_row_updates_to_profile = 1



    0.018 test_updating_many_rows_in_public_filtered_views  test_public_sharing_perform
└─ 0.018 update_row_by_id  baserow/contrib/database/rows/handler.py:426
   ├─ 0.015 send  django/dispatch/dispatcher.py:159
   │     [2 frames hidden]  django
   │        0.015 <listcomp>  django/dispatch/dispatcher.py:180
   │        ├─ 0.009 public_before_row_update  baserow/contrib/database/ws/public/rows
   │        │  ├─ 0.004 get_public_views_row_checker  baserow/contrib/database/views/han
   │        │  │  └─ 0.004 __init__  baserow/contrib/database/views/handler.py:985
   │        │  │     ├─ 0.002 apply_filters  baserow/contrib/database/views/handler.py:2
   │        │  │     │  └─ 0.002 apply_to_queryset  baserow/contrib/database/fields/fiel
   │        │  │     │     └─ 0.002 filter  django/db/models/query.py:935
   │        │  │     │           [14 frames hidden]  django
   │        │  │     └─ 0.002 __iter__  django/db/models/query.py:265
   │        │  │           [16 frames hidden]  django
   │        │  │              0.001 get_prefetch_queryset  django/db/models/fields/relat
   │        │  │              └─ 0.001 get_queryset  baserow/core/managers.py:29
   │        │  │                 └─ 0.001 filter  django/db/models/query.py:935
   │        │  │                       [9 frames hidden]  django
   │        │  ├─ 0.003 _serialize_row  baserow/contrib/database/ws/public/rows/signals
   │        │  │  ├─ 0.002 data  rest_framework/serializers.py:546
   │        │  │  │     [18 frames hidden]  rest_framework, django, copy, <built-in>
   │        │  │  └─ 0.001 get_row_serializer_class  baserow/contrib/database/api/rows/
   │        │  │     └─ 0.001 get_response_serializer_field  baserow/contrib/database/fi
   │        │  └─ 0.002 get_filtered_views_where_row_is_visible  baserow/contrib/databas
   │        │     └─ 0.002 _check_row_visible  baserow/contrib/database/views/handler.py
   │        │        └─ 0.002 exists  django/db/models/query.py:806
   │        │              [19 frames hidden]  django, copy
   │        ├─ 0.003 public_row_updated  baserow/contrib/database/ws/public/rows/signals
   │        │  ├─ 0.002 _serialize_row  baserow/contrib/database/ws/public/rows/signals.
   │        │  │  ├─ 0.001 get_row_serializer_class  baserow/contrib/database/api/rows/s
   │        │  │  │  └─ 0.001 get_response_serializer_field  baserow/contrib/database/fi
   │        │  │  │     └─ 0.001 get_serializer_field  baserow/contrib/database/fields/f
   │        │  │  │        └─ 0.001 __init__  rest_framework/fields.py:773
   │        │  │  │              [3 frames hidden]  rest_framework
   │        │  │  └─ 0.001 data  rest_framework/serializers.py:546
   │        │  │        [15 frames hidden]  rest_framework, django, copy, <built-in>
   │        │  └─ 0.001 on_commit  django/db/transaction.py:123
   │        │        [7 frames hidden]  django, asgiref
   │        └─ 0.003 before_row_update  baserow/contrib/database/ws/rows/signals.py:37
   │           ├─ 0.002 data  rest_framework/serializers.py:546
   │           │     [13 frames hidden]  rest_framework, django, copy
   │           └─ 0.001 get_row_serializer_class  baserow/contrib/database/api/rows/seri
   │              └─ 0.001 get_serializer_class  baserow/api/utils.py:254
   ├─ 0.002 get  django/db/models/query.py:414
   │     [18 frames hidden]  django
   └─ 0.001 save  django/db/models/base.py:672
         [11 frames hidden]  django

    """
