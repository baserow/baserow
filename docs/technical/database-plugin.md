# Database plugin

The database plugin is installed by default in every copy of Baserow. Without it you 
can't really do anything with the application. In short this is the plugin that allows
creating a database with a spreadsheet-like interface. You will notice that everything
has been built around this concept.

## Tables

Each database application can have multiple tables and a table is exactly what you
might suspect. It contains rows and columns, but in Baserow the columns are called fields. 
Every table has its own schema representation in the PostgreSQL database.

There is a `baserow.contrib.database.table.handler.TableHandler` handler class that has
all kinds of methods related to creating, modifying, and deleting tables. Another nice
thing is that a Django model of the table can easily be generated. Let's say you have 
the following table with id `id` and you want select all the data.

| Model name | Brand | Price |
|------------|-------|-------|
| 3 Series   | BTW   | 30000 |
| A4         | Audi  | 25000 |
| Model 3    | Tesla | 50000 |

```python
from baserow.contrib.database.table.models import Table

cars_table = Table.objects.get(pk=ID_REFERENCED_TABLE_ABOVE)
# If you set the attribute_names to True the attribute name is going to be the field 
# name provided by the user instead of field_{id}
cars_model = cars_table.get_model(attribute_names=True)

for car in cars_model.objects.all():
    print(car.id, car.model_name, car.price)

# Results in:
# 1 3 series 30000
# 2 A4 30000
# 2 Model 3 30000
```

## Fields

A field is actually a column definition of a table. It accepts only a certain data type 
for its cell values. A field can, for example, be a number field that accepts two
placements after the comma. If a new field is added to a table it is also added as
column to the table  representation in the database. The column name in the database
will be field_{id}. The fields can be created, modified and deleted via the 
`baserow.contrib.database.fields.handler.FieldHandler` and via the REST API. Several 
field types have been included by default.

> Field types can be added via plugins. More about that on the 
> [field type plugin page](../plugins/field-type.md).

* `text`: Single line text.
* `long_text`: Multi line text.
* `number`: A number that can optionally be negative and optionally be a decimal.
* `boolean`: Just holds true or false.
* `date`: A date field in EU, ISO or USA format that can optionally include time am/pm 
  format.

## Views

Views define how the table data is displayed to the user. By default the `grid` view 
type is included, which displays the data in a spreadsheet-like interface. Multiple
views can be added to each table and each view has its own settings. If you, for
example, have two grid views, A and B, of the same table of data, and you change the
width of a column in grid A, then it only changes for grid A and not for grid B. The
views can be created, modified and deleted via the 
`baserow.contrib.database.views.handler.ViewHandler` and via the REST API.
The [collapsible grid group-by note](./collapsible-grid-group-by.md) explains how
large grouped grid views are paged and rendered.

> View types can be added via plugins. More about that on the 
> [view type plugin page](../plugins/view-type.md).

### Rows

Rows are the table data. The values that are accepted depend on the fields of the 
table. The data is stored in the representation table in the database. In the example 
below we will insert a single row of data in a table we have just created via the 
python shell. The same result could be achieved via the REST API.

```python
from django.contrib.auth import get_user_model 
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler

User = get_user_model()
user = User.objects.get(pk=1)
table = Table.objects.get(pk=10)

name = FieldHandler().create_field(user, table, 'text', name='Name')
price = FieldHandler().create_field(user, table, 'number', name='Price')
row = RowHandler().create_row(user, table, {
    f'field_{name.id}': 'Smartphone',
    f'field_{price.id}': 300
})

model = table.get_model()
rows = model.objects.all()

print(rows[0].name)
print(rows[0].price)

# Which will result in:
# Smartphone
# 300
```
