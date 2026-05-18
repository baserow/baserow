# View filter type

!!! danger "Legacy plugin system"

    This page is historical and does not work with current Baserow. See
    [Plugin basics](introduction.md) for the supported alternative.

A view filter can be created by a user to filter the rows of a view. Only the rows that
apply to the filters are going to be displayed. There can be many types of filters like
equals, contains, lower than, is empty, etc. These filter types can easily be added when
creating a plugin.

## Backend

We are going to create a really simple `equals` filter. This filter already exists, but
because of its simplicity we are going to use it as an example. In your filter class you
can define compatible field types. It will only be possible to create a filter in
combination with those field types. The `get_filter` method should return a
Django `models.Q` object which will automatically be added to the correct queryset.
Because the field name is provided we can easily do a `Q(**{field_name: value})`
comparison with the provided value.

plugins/my_baserow_plugin/backend/src/my_baserow_plugin/view_filters.py
```python
from django.db.models import Q

from baserow.contrib.database.views.registries import ViewFilterType


class EqualToViewFilterType(ViewFilterType):
    type = 'equal_to'
    compatible_field_types = ['text']

    def get_filter(self, field_name, value, model_field, field):
        value = value.strip()

        # If an empty value has been provided we do not want to filter at all.
        if value == '':
            return Q()

        # Check if the model_field accepts the value.
        try:
            value = model_field.get_prep_value(value)
            return Q(**{field_name: value})
        except Exception:
            pass

        return Q()
```

Finally, we need to register the view filter in the registry.

plugins/my_baserow_plugin/backend/src/my_baserow_plugin/config.py
```python
from django.apps import AppConfig

from baserow.core.registries import plugin_registry
from baserow.contrib.database.views.registries import view_filter_type_registry


class PluginNameConfig(AppConfig):
    name = 'my_baserow_plugin'

    def ready(self):
        from .plugins import PluginNamePlugin
        from .view_filters import EqualToViewFilterType

        plugin_registry.register(PluginNamePlugin())
        view_filter_type_registry.register(EqualToViewFilterType())
```

### API request

After creating the filter type you can create a filter by making the following API
request. Note that you must already have a grid view that contains some fields.

```
POST /api/database/views/{view_id}/filters/
Host: api.baserow.io
Content-Type: application/json

{
  "field": {field_id},
  "type": "equal_to",
  "value": "Example"
}
```
or
```
curl -X POST -H 'Content-Type: application/json' -i https://api.baserow.io/api/database/views/{view_id}/filters/ --data '{
  "field": {field_id},
  "type": "equal_to",
  "value": "Example"
}'
```

Now that the filter has been created you can refresh your grid view by calling the
`list_database_table_grid_view_rows endpoint`. It will now only contain the rows that
apply to the filter.

```
GET /api/database/views/grid/{view_id}/
Host: api.baserow.io
Content-Type: application/json
```
or
```
curl -X GET -H 'Content-Type: application/json' -i https://api.baserow.io/api/database/views/grid/{view_id}/'
```

## Web frontend

This filter also needs to be added to the web frontend, otherwise it does not know the
filter exists. You can add the filter by creating a new `ViewFilterType` class and
register it with the `viewFilter` registry. the `getName` method should return a string
that is visible to the user when choosing the filter. The `getInputComponent` method
handles the user input of the value. By default no input is shown. The
`getCompatibleFieldTypes` should return a list of field type names that are compatible
with the filter. The last method is named `matches` and we use this to check if a value
is compatible applies to the filter in real time.

It is unfortunate that we need to have the same code in two places, but because the
filtering needs to happen at the backend and frontend for real time comparison we do
need this. More specifically the frontend uses the filtering code to check if after a
row is edited if it still matches the views current filters. If it doesn't then a
warning will be displayed to the user that if they save their edit, the row will be
filtered out of view.

plugins/my_baserow_plugin/web-frontend/viewTypes.js
```javascript
import { ViewFilterType } from '@baserow/modules/database/viewFilters'
import ViewFilterTypeText from '@baserow/modules/database/components/view/ViewFilterTypeText'

export class EqualViewFilterType extends ViewFilterType {
  static getType() {
    return 'equal_to'
  }

  getName() {
    return 'is 2'
  }

  getInputComponent() {
    // The component that handles the value input, in this case we use the existing
    // text input, but it is also possible to create a custom component. It should
    // follow v-model principle.
    return ViewFilterTypeText
  }

  getCompatibleFieldTypes() {
    return ['text']
  }

  matches(rowValue, filterValue) {
    if (rowValue === null) {
      rowValue = ''
    }

    rowValue = rowValue.toString().toLowerCase().trim()
    filterValue = filterValue.toString().toLowerCase().trim()
    return filterValue === '' || rowValue === filterValue
  }
}
```

plugins/my_baserow_plugin/web-frontend/plugin.js
```javascript
import { PluginNamePlugin } from '@my-baserow-plugin/plugins'
import { EqualViewFilterType } from '@my-baserow-plugin/viewFilters'

export default (context) => {
  const { app } = context
  app.$registry.register('plugin', new PluginNamePlugin(context))
  app.$registry.register('viewFilter', new EqualViewFilterType(context))
}
```

Once you have added this code, a new filter to a view and have selected a
text field you should be able to select the `is 2` filter. It should also be possible to
provide a text value to compare the field value with.
