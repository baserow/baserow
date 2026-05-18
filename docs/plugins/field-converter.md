# Field converter

!!! danger "Legacy plugin system"

    This page is historical and does not work with current Baserow. See
    [Plugin basics](introduction.md) for the supported alternative.

A field converter can alter a field's database schema and convert the related data to a
new format. For example in Django it is not possible to alter a ManyToManyField to a
CharField or to convert from and to a ManyToManyField. The alter_field function of the
schema editor would not work in this case. If you want to convert it you have to create
a new column and remove the old one instead of altering. This is something that you do
with a field converter.

## How it works

When the field type changes or a field's property changes Baserow will check if there is
an applicable converter. It does so by looping over the registered field converters,
calling the `is_applicable` method which determines based on the `from`
and `to` field instances if the converter can be applied in the situation. If an
applicable converter is found it will be used. It could be that there are multiple
converters applicable, but it will use the first one that can be applied. If there are
not any converters applicable then the regular lenient schema editor's alter_field
method will be used.

## An example

In the example below we are going to check if the from_field is a text field and if the
to_field is a date field. If that is the case we first want to remove the old field and
then create the new field instead of using the lenient schema editor's alter_field
method. Of course this would not make sense in real life, but it is just to demonstrate
how a converter could work. You can of course be really creative in the alter_field
method of your converter. You can for example first load all the old values in memory
before removing the field and later update them again after the new field has been
added. You can also first create the new field, perform some query that updates the data
of the field based on the old field and then delete the old field and rename the new
field. A lot is possible. We do recommend to keep performance in mind. Ask yourself the
question does it stay fast if there are 100k rows?

plugins/my_baserow_plugin/backend/src/my_baserow_plugin/field_converters.py

```python
from baserow.contrib.database.fields.field_types import (
    TextFieldType, DateFieldType
)
from baserow.contrib.database.fields.registries import FieldConverter


class TextToDateFieldConverter(FieldConverter):
    type = 'text-to-date'

    def is_applicable(self, from_model, from_field, to_field):
        return (
                isinstance(from_field, TextFieldType) and
                isinstance(to_field, DateFieldType)
        )

    def alter_field(self, from_field, to_field, from_model, to_model,
                    from_model_field, to_model_field, user, connection):
        with safe_django_schema_editor() as schema_editor:
            schema_editor.remove_field(from_model, from_model_field)
            schema_editor.add_field(to_model, to_model_field)
```

plugins/my_baserow_plugin/backend/src/my_baserow_plugin/config.py

```python
from django.apps import AppConfig

from baserow.contrib.database.fields.registries import field_converter_registry


class PluginNameConfig(AppConfig):
    name = 'my_baserow_plugin'

    def ready(self):
        from .field_converters import TextToDateFieldConverter

        field_converter_registry.register(TextToDateFieldConverter())
