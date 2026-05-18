# Field type

!!! danger "Legacy plugin system"

    This page is historical and does not work with current Baserow. See
    [Plugin basics](introduction.md) for the supported alternative.

A field is an abstraction that defines how table data is stored per column. More
information can be found on the
[database plugin page](../technical/database-plugin.md). This is a tutorial about how to
create your own custom table field type for Baserow via a plugin. We are going to create
a integer field which displays as "hello world". Of course a number field with the more
features already exists, this is just for example purposes. In the end the user can
create an integer field that only shows a hello world message. We expect that you are
using the [plugin boilerplate](./boilerplate.md).

## Backend

We are going to start by creating an `IntegerField` model that extends the `Field`
model. It will have a property to indicate if a negative number is allowed which can be
set for each field that is created.

Create `plugins/my_baserow_plugin/backend/src/my_baserow_plugin/models.py`

```python
from django.db import models

from baserow.contrib.database.fields.models import Field


class IntegerField(Field):
    integer_negative = models.BooleanField(default=False)

```

Depending on the field model instance a model and serializer field must be returned. The
model field is used when generating the table's model that is used to select and update
the data. The serializer field is used when exposing the data via the REST API to the
web-frontend. For more information about the properties and methods related to the field
type you can check the
`FieldType` class in
`backend/src/baserow/contrib/database/fields/registries.py`.

Create `plugins/my_baserow_plugin/backend/src/my_baserow_plugin/field_types.py`

```python
from django.db import models
from django.core.exceptions import ValidationError

from rest_framework import serializers

from baserow.contrib.database.fields.registries import FieldType

from .models import IntegerField


class IntegerFieldType(FieldType):
    type = 'integer'
    model_class = IntegerField
    allowed_fields = ['integer_negative']
    serializer_field_names = ['integer_negative']

    def prepare_value_for_db(self, instance, value):
        if value and not instance.integer_negative and value < 0:
            raise ValidationError(f'The value for field {instance.id} cannot be '
                                  f'negative.')
        return value

    def get_serializer_field(self, instance, **kwargs):
        return serializers.IntegerField(required=False, allow_null=True)

    def get_model_field(self, instance, **kwargs):
        return models.IntegerField(null=True, blank=True)
```

Create `plugins/my_baserow_plugin/backend/src/my_baserow_plugin/config.py`

```python
from django.apps import AppConfig

from baserow.core.registries import plugin_registry
from baserow.contrib.database.fields.registries import field_type_registry


class PluginNameConfig(AppConfig):
    name = 'my_baserow_plugin'

    def ready(self):
        from .plugins import PluginNamePlugin
        from .field_types import IntegerFieldType

        plugin_registry.register(PluginNamePlugin())
        field_type_registry.register(IntegerFieldType())
```

Finally, lets start the dev environment and use it to apply the
migrations because we have created a new model.

```bash
# Set these env vars to make sure mounting your source code into the container uses
# the correct user and permissions.
export PLUGIN_BUILD_UID=$(id -u)
export PLUGIN_BUILD_GID=$(id -g)
docker-compose run my-baserow-plugin /baserow.sh backend-cmd manage makemigrations
docker-compose run my-baserow-plugin /baserow.sh backend-cmd manage migrate
```

## Web frontend

Because the backend and web-frontend are two separate applications that only communicate
via a REST API with each other, the web-frontend does not yet know about the existence
of the `integer` field type. We can add this in a similar way. Add/modify the following
files in the web-frontend part of the plugin.

plugins/my_baserow_plugin/web-frontend/fieldTypes.js

```javascript
import { FieldType } from "@baserow/modules/database/fieldTypes";

import SubFormIntegerField from "@my-baserow-plugin/components/SubFormIntegerField";
import GridViewIntegerField from "@my-baserow-plugin/components/GridViewIntegerField";
import RowEditIntegerField from "@my-baserow-plugin/components/RowEditIntegerField";

export class IntegerFieldType extends FieldType {
    static getType() {
        return "integer";
    }

    getIconClass() {
        return "iconoir-numbered-list-left";
    }

    getName() {
        return "Integer";
    }

    getFormComponent() {
        return SubFormIntegerField;
    }

    getGridViewFieldComponent() {
        return GridViewIntegerField;
    }

    getRowEditFieldComponent(field) {
        return RowEditIntegerField;
    }
}
```

`plugins/my_baserow_plugin/web-frontend/plugin.js`

```javascript
import { PluginNamePlugin } from "@my-baserow-plugin/plugins";
import { IntegerFieldType } from "@my-baserow-plugin/fieldTypes";

export default (context) => {
    const { app } = context;
    app.$registry.register("plugin", new PluginNamePlugin(context));
    app.$registry.register("field", new IntegerFieldType(context));
};
```

The GridViewIntegerField component is returned by the `getGridViewFieldComponent`
method of the `IntegerFieldType` class which means that this component is added for each
data row field that has the `integer` type. For now we only add "Hello World" for
example purposes so it doesn't actually display the number, but there are plenty of
examples in the Baserow repository in the directory
`web-frontend/modules/database/components/view/grid`.

plugins/my_baserow_plugin/web-frontend/components/GridViewIntegerField.vue

```vue
<template>
    <div class="grid-view__cell" :class="{ active: selected }">
        <div>Hello World</div>
    </div>
</template>

<script>
import gridField from "@baserow/modules/database/mixins/gridField";

export default {
    mixins: [gridField],
};
</script>
```

The `RowEditIntegerField` component is returned by the `getRowEditFieldComponent`
method of the `IntegerFieldType` class which means that this component is added in the
popup row form. This form is shown when the expand icon on the left side of row has been
clicked by the user. For now, we only add "Hello World" for example purposes, but there
are plenty of examples in the Baserow repository in the
directory `web-frontend/modules/database/components/row`.

`plugins/my_baserow_plugin/web-frontend/components/RowEditIntegerField.vue`

```vue
<template>
    <div class="control__elements">Hello World</div>
</template>

<script>
import rowEditField from "@baserow/modules/database/mixins/rowEditField";

export default {
    mixins: [rowEditField],
};
</script>
```

The `SubFormIntegerField` component will be added to the context menu form when creating
or editing a field. If there are extra properties defined in the related model in the
backend then they can be added to the form using this component.

`plugins/my_baserow_plugin/web-frontend/components/SubFormIntegerField.vue`

```vue
<template>
    <div>
        <div class="control">
            <div class="control__elements">
                <Checkbox v-model="values.integer_negative"
                    >Allow negative</Checkbox
                >
            </div>
        </div>
    </div>
</template>

<script>
import form from "@baserow/modules/core/mixins/form";

export default {
    name: "SubFormIntegerField",
    mixins: [form],
    data() {
        return {
            allowedValues: ["integer_negative"],
            values: { integer_negative: false },
        };
    },
    methods: {
        isFormValid() {
            return true;
        },
    },
};
</script>
```

After adding all the files you should be able to create a field with the newly created
integer field type.
