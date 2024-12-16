from django.contrib.contenttypes.models import ContentType
from django.db import models

import pytest

from baserow.contrib.database.fields.models import get_default_field_content_type
from baserow.contrib.database.views.models import View
from baserow.core.mixins import PolymorphicContentTypeMixin
from baserow.core.models import Application


@pytest.mark.django_db
def test_get_all_parents_and_self_with_single_model(data_fixture):
    class TmpModel(PolymorphicContentTypeMixin, models.Model):
        name = models.CharField()
        content_type = models.ForeignKey(
            ContentType,
            verbose_name="content type",
            related_name="database_fields",
            on_delete=models.SET(get_default_field_content_type),
        )

        class Meta:
            app_label = "test"

    model = TmpModel(name="a")
    assert model.all_parents_and_self() == [model]


@pytest.mark.django_db
def test_get_all_parents_and_self_with_one_level_of_inheritance(data_fixture):
    class RootParent(PolymorphicContentTypeMixin, models.Model):
        name = models.CharField()
        content_type = models.ForeignKey(
            ContentType,
            verbose_name="content type",
            related_name="database_fields",
            on_delete=models.CASCADE,
        )

        class Meta:
            app_label = "test"

    class SubModel(RootParent):
        class Meta:
            app_label = "test"

    parent_model = RootParent(name="a")
    model = SubModel(name="a", rootparent_ptr=parent_model)
    assert model.all_parents_and_self() == [parent_model, model]
    assert parent_model.all_parents_and_self() == [parent_model]


@pytest.mark.django_db
def test_get_all_parents_and_self_with_two_levels_of_inheritance(data_fixture):
    class RootParent2(PolymorphicContentTypeMixin, models.Model):
        name = models.CharField()
        content_type = models.ForeignKey(
            ContentType,
            verbose_name="content type",
            related_name="database_fields",
            on_delete=models.CASCADE,
        )

        class Meta:
            app_label = "test"

    class SubModel2(RootParent2):
        class Meta:
            app_label = "test"

    class SubSubModel(SubModel2):
        class Meta:
            app_label = "test"

    parent_model = RootParent2(name="a")
    sub_model = SubModel2(name="a", rootparent2_ptr=parent_model)
    sub_sub_model = SubSubModel(name="a", submodel2_ptr=sub_model)
    assert sub_sub_model.all_parents_and_self() == [
        parent_model,
        sub_model,
        sub_sub_model,
    ]
    assert sub_model.all_parents_and_self() == [
        parent_model,
        sub_model,
    ]
    assert parent_model.all_parents_and_self() == [
        parent_model,
    ]


@pytest.mark.django_db
def test_cant_define_model_with_multiple_parents_with_poly_mixin(data_fixture):
    class ParentA(PolymorphicContentTypeMixin, models.Model):
        name = models.CharField()
        content_type = models.ForeignKey(
            ContentType,
            verbose_name="content type",
            related_name="database_fields",
            on_delete=models.CASCADE,
        )

        class Meta:
            app_label = "test"

    class ParentB(PolymorphicContentTypeMixin, models.Model):
        other = models.CharField()
        content_type = models.ForeignKey(
            ContentType,
            verbose_name="content type",
            related_name="database_fields",
            on_delete=models.CASCADE,
        )

        class Meta:
            app_label = "test"

    class SubModel3(ParentA, ParentB):
        class Meta:
            app_label = "test"

    with pytest.raises(AttributeError, match="does not support multiple inheritance"):
        SubModel3(name="a")


@pytest.mark.django_db
def test_specific_remembers_select_related(data_fixture, django_assert_num_queries):
    database = data_fixture.create_database_application()

    application = Application.objects.select_related("workspace").get(pk=database.id)

    with django_assert_num_queries(1):
        specific_application = application.specific
        assert specific_application.workspace.id == database.workspace_id


@pytest.mark.django_db
def test_specific_remembers_prefetch_related(data_fixture, django_assert_num_queries):
    grid_view = data_fixture.create_grid_view()
    filter_1 = data_fixture.create_view_filter(view=grid_view)
    filter_2 = data_fixture.create_view_filter(view=grid_view)

    views = list(
        View.objects.filter(pk=grid_view.id).prefetch_related("viewfilter_set")
    )

    with django_assert_num_queries(1):
        specific_view = views[0].specific
        filters = list(specific_view.viewfilter_set.all())
        assert filters[0].id == filter_1.id
        assert filters[1].id == filter_2.id
