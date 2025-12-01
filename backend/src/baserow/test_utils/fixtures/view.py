from rest_framework import serializers

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.views.exceptions import DecoratorTypeAlreadyRegistered
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import (
    FormView,
    FormViewFieldOptions,
    FormViewFieldOptionsCondition,
    FormViewFieldOptionsConditionGroup,
    GalleryView,
    GalleryViewFieldOptions,
    GridView,
    GridViewFieldOptions,
    ViewDecoration,
    ViewFilter,
    ViewFilterGroup,
    ViewGroupBy,
    ViewSort,
)
from baserow.contrib.database.views.registries import (
    DecoratorType,
    DecoratorValueProviderType,
    decorator_type_registry,
    decorator_value_provider_type_registry,
)


class TmpDecoratorType1(DecoratorType):
    type = "tmp_decorator_type_1"


class TmpDecoratorType2(DecoratorType):
    type = "tmp_decorator_type_2"


class TmpDecoratorType3(DecoratorType):
    type = "tmp_decorator_type_3"


class ValueProviderSerializer1(serializers.Serializer):
    field_id = serializers.IntegerField(allow_null=True)


class ValueProviderSerializer2(serializers.Serializer):
    description = serializers.CharField(required=True)


class ValueProviderType1(DecoratorValueProviderType):
    type = "value_provider_1"
    compatible_decorator_types = [TmpDecoratorType1.type, TmpDecoratorType2.type]
    value_provider_conf_serializer_class = ValueProviderSerializer1


class ValueProviderType2(DecoratorValueProviderType):
    type = "value_provider_2"
    compatible_decorator_types = [TmpDecoratorType1.type, TmpDecoratorType2.type]
    value_provider_conf_serializer_class = ValueProviderSerializer2


class ValueProviderType3(DecoratorValueProviderType):
    type = "value_provider_3"
    compatible_decorator_types = []
    value_provider_conf_serializer_class = ValueProviderSerializer1


class ViewFixtures:
    def create_grid_view(self, user=None, create_options=True, **kwargs):
        if "table" not in kwargs:
            kwargs["table"] = self.create_database_table(user=user)

        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "order" not in kwargs:
            kwargs["order"] = 0

        grid_view = GridView.objects.create(**kwargs)
        if create_options:
            self.create_grid_view_field_options(grid_view)
        return grid_view

    def create_grid_view_field_options(self, grid_view, **kwargs):
        return [
            self.create_grid_view_field_option(grid_view, field, **kwargs)
            for field in Field.objects.filter(table=grid_view.table)
        ]

    def create_grid_view_field_option(self, grid_view, field, **kwargs):
        field_options, _ = GridViewFieldOptions.objects.update_or_create(
            grid_view=grid_view, field=field, defaults=kwargs
        )
        return field_options

    def create_gallery_view(self, user=None, create_options=True, **kwargs):
        if "table" not in kwargs:
            kwargs["table"] = self.create_database_table(user=user)

        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "order" not in kwargs:
            kwargs["order"] = 0

        gallery_view = GalleryView.objects.create(**kwargs)
        if create_options:
            self.create_gallery_view_field_options(gallery_view)
        return gallery_view

    def create_gallery_view_field_options(self, gallery_view, **kwargs):
        return [
            self.create_gallery_view_field_option(gallery_view, field, **kwargs)
            for field in Field.objects.filter(table=gallery_view.table)
        ]

    def create_gallery_view_field_option(self, gallery_view, field, **kwargs):
        field_options, _ = GalleryViewFieldOptions.objects.update_or_create(
            gallery_view=gallery_view, field=field, defaults=kwargs
        )
        return field_options

    def create_form_view(self, user=None, **kwargs):
        if "table" not in kwargs:
            kwargs["table"] = self.create_database_table(user=user)

        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "order" not in kwargs:
            kwargs["order"] = 0

        form_view = FormView.objects.create(**kwargs)
        self.create_form_view_field_options(form_view)
        return form_view

    def create_form_view_field_options(self, form_view, **kwargs):
        return [
            self.create_form_view_field_option(form_view, field, **kwargs)
            for field in Field.objects.filter(table=form_view.table)
            if field.get_type().can_be_in_form_view
        ]

    def create_form_view_field_option(self, form_view, field, **kwargs):
        field_options, _ = FormViewFieldOptions.objects.update_or_create(
            form_view=form_view, field=field, defaults=kwargs
        )
        return field_options

    def create_form_view_field_options_condition_group(self, user=None, **kwargs):
        if "field_option" not in kwargs:
            form_view = self.create_form_view(user)
            kwargs["field_options"] = self.create_form_view_field_option(
                form_view=form_view, field=kwargs["field"]
            )

        return FormViewFieldOptionsConditionGroup.objects.create(**kwargs)

    def create_form_view_field_options_condition(self, user=None, **kwargs):
        if "field" not in kwargs:
            kwargs["field"] = self.create_text_field(table=kwargs["view"].table)

        if "field_option" not in kwargs:
            form_view = self.create_form_view(user)
            kwargs["field_options"] = self.create_form_view_field_option(
                form_view=form_view, field=kwargs["field"]
            )

        if "type" not in kwargs:
            kwargs["type"] = "equal"

        if "value" not in kwargs:
            kwargs["value"] = self.fake.name()

        return FormViewFieldOptionsCondition.objects.create(**kwargs)

    def create_view_filter_group(self, user=None, **kwargs):
        if "view" not in kwargs:
            kwargs["view"] = self.create_grid_view(user)

        return ViewFilterGroup.objects.create(**kwargs)

    def create_view_filter(self, user=None, **kwargs):
        if "view" not in kwargs:
            kwargs["view"] = self.create_grid_view(user)

        if "field" not in kwargs:
            kwargs["field"] = self.create_text_field(table=kwargs["view"].table)

        if "type" not in kwargs:
            kwargs["type"] = "equal"

        if "value" not in kwargs:
            kwargs["value"] = self.fake.name()

        return ViewFilter.objects.create(**kwargs)

    def create_view_sort(self, user=None, **kwargs):
        if "view" not in kwargs:
            kwargs["view"] = self.create_grid_view(user)

        if "field" not in kwargs:
            kwargs["field"] = self.create_text_field(table=kwargs["view"].table)

        if "order" not in kwargs:
            kwargs["order"] = "ASC"

        return ViewSort.objects.create(**kwargs)

    def create_view_group_by(self, user=None, **kwargs):
        if "view" not in kwargs:
            kwargs["view"] = self.create_grid_view(user)

        if "field" not in kwargs:
            kwargs["field"] = self.create_text_field(table=kwargs["view"].table)

        if "order" not in kwargs:
            kwargs["order"] = "ASC"

        return ViewGroupBy.objects.create(**kwargs)

    def register_temp_decorators_and_value_providers(self):
        try:
            decorator_type_registry.register(TmpDecoratorType1())
            decorator_type_registry.register(TmpDecoratorType2())
            decorator_type_registry.register(TmpDecoratorType3())
            decorator_value_provider_type_registry.register(ValueProviderType1())
            decorator_value_provider_type_registry.register(ValueProviderType2())
            decorator_value_provider_type_registry.register(ValueProviderType3())
        except DecoratorTypeAlreadyRegistered:
            pass

    def create_view_decoration(self, user=None, **kwargs):
        self.register_temp_decorators_and_value_providers()

        if "view" not in kwargs:
            kwargs["view"] = self.create_grid_view(user)

        if "type" not in kwargs:
            kwargs["type"] = "tmp_decorator_type_1"

        if "value_provider_type" not in kwargs:
            kwargs["value_provider_type"] = "value_provider_1"

        if "value_provider_conf" not in kwargs:
            kwargs["value_provider_conf"] = {}

        if "order" not in kwargs:
            kwargs["order"] = 0

        return ViewDecoration.objects.create(**kwargs)

    def create_public_password_protected_grid_view(
        self, user=None, password=None, **kwargs
    ):
        view = self.create_grid_view(user=user, public=True, **kwargs)
        if password:
            view.set_password(password)
            view.save()
        return view

    def create_public_password_protected_grid_view_with_token(
        self, user=None, password=None, **kwargs
    ):
        view = self.create_public_password_protected_grid_view(
            user=user, password=password, **kwargs
        )
        token = ViewHandler().encode_public_view_token(view)
        return view, token

    def create_public_password_protected_form_view(
        self, user=None, password=None, **kwargs
    ):
        view = self.create_form_view(user=user, public=True, **kwargs)
        if password:
            view.set_password(password)
            view.save()
        return view
