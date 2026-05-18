# View type

!!! danger "Legacy plugin system"

    This page is historical and does not work with current Baserow. See
    [Plugin basics](introduction.md) for the supported alternative.

A view is an abstraction that defines how table data is displayed to a user. More 
information about this can be found on the 
[database plugin page](../technical/database-plugin.md). This is a tutorial about 
how to create your own custom table view type for Baserow via a plugin. We are going to
create a calendar view that doesn't really do anything. In the end the user can create 
a new calendar view that only shows a hello world message. We expect that you are 
using the [plugin boilerplate](./boilerplate.md).

## Backend

We are going to start by creating a `CalendarView` model that extends the `View` model.
Every time the user creates a new calendar view a new instance of the CalendarView will
be created. If there are any unique properties that the user must be able to configure
per view they can be set here. Even though we are not going to add unique properties in
this tutorial you could for example store which field is the date field, or if there
are fields that must be hidden.

plugins/my_baserow_plugin/backend/src/my_baserow_plugin/models.py
```python
from baserow.contrib.database.views.models import View


class CalendarView(View):
    pass
```

Next we need to create a `CalendarViewType` class. All the view type configuration,
hooks and other related things are in here. More information about the possibilities 
can be found in the Baserow repository at 
the `ViewType` class in
`backend/src/baserow/contrib/database/views/registries.py`.

plugins/my_baserow_plugin/backend/src/my_baserow_plugin/view_types.py
```python
from baserow.contrib.database.views.registries import ViewType

from .models import CalendarView


class CalendarViewType(ViewType):
    type = 'calendar'
    model_class = CalendarView
```

Finally we need to register the view type in the registry.

plugins/my_baserow_plugin/backend/src/my_baserow_plugin/config.py
```python
from django.apps import AppConfig

from baserow.core.registries import plugin_registry
from baserow.contrib.database.views.registries import view_type_registry


class PluginNameConfig(AppConfig):
    name = 'my_baserow_plugin'

    def ready(self):
        from .plugins import PluginNamePlugin
        from .view_types import CalendarViewType

        plugin_registry.register(PluginNamePlugin())
        view_type_registry.register(CalendarViewType())
```

Don't forget to create and apply the migrations because we have created a new model.

```
# Set these env vars to make sure mounting your source code into the container uses
# the correct user and permissions.
export PLUGIN_BUILD_UID=$(id -u)
export PLUGIN_BUILD_GID=$(id -g)
docker-compose -f docker-compose.dev.yml run --rm my-baserow-plugin backend-cmd manage makemigrations
docker-compose -f docker-compose.dev.yml run --rm my-baserow-plugin backend-cmd manage migrate
```

## Web frontend

Because the backend and web-frontend are two separate applications that only 
communicate via a REST API with each other, the web-frontend does not yet know about 
the existence of the `calendar` view type. We can add this in a similar way. Add/modify
the following files in the web-frontend part of the plugin.

plugins/my_baserow_plugin/web-frontend/components/CalendarView.vue
```vue
<template>
  <div>Hello World</div>
</template>

<script>
export default {
  name: 'CalendarView',
  props: {
    primary: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
  },
}
</script>
```

You can inspect the `ViewType` class in
`web-frontend/modules/database/viewTypes.js` for all the methods and properties that
can be overridden here. The component returned by `getComponent` is added to the body
of the page when a view of this type is selected.

plugins/my_baserow_plugin/web-frontend/viewTypes.js
```javascript
import { ViewType } from '@baserow/modules/database/viewTypes'
import CalendarView from '@my-baserow-plugin/components/CalendarView'

export class CalendarViewType extends ViewType {
  static getType() {
    return 'calendar'
  }

  getIconClass() {
    return 'iconoir-calendar'
  }

  getName() {
    return 'Calendar'
  }

  getComponent() {
    return CalendarView
  }
}
```

plugins/my_baserow_plugin/web-frontend/plugin.js
```javascript
import { PluginNamePlugin } from '@my-baserow-plugin/plugins'
import { CalendarViewType } from '@my-baserow-plugin/viewTypes'

export default (context) => {
  const { app } = context
  app.$registry.register('plugin', new PluginNamePlugin(context))
  app.$registry.register('view', new CalendarViewType(context))
}
```

Once you have added this code you should be able to click on the "Calendar" button
in the views context menu next to "Add a view". A popup should appear and if you fill
out the form the calendar view should be created. You can then click on the newly 
created view and in the body of the page you should see "Hello World".
