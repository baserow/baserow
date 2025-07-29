# Baserow Documentation

Source: https://baserow.io/user-docs/rollup-field

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Rollup field

A rollup field in Baserow allows you to aggregate data and gain valuable insights from linked tables. It performs calculations on rows from a [linked table](/user-docs/link-to-table-field).

## Using the rollup field

A rollup field performs calculations with the linked values. For example, it can sum together all the values from the linked rows or return only the maximum value.

## Create a rollup field

> The rollup field can only be used when you have a [link to table](/user-docs/link-to-table-field) field in your table. To use a rollup field, create a link to table field that’s linked to another table in your database.

To add a rollup field to your table:

  * Within your database, select the table where you want to add the rollup field.
  * Click on the `+` button located on the far-right side of the table to [add a new field](/user-docs/adding-a-field).
  * Input the name of the field.
  * In the field options, select “Rollup” from the list of field types.
  * In the configuration panel, select the link to table field from which you want to roll up the data. This is the table that contains the related rows you want to perform calculations on. If you have multiple link to table fields, select which field on the table is linked to the rows you want to roll up.
  * Select a field from the linked table that you want to include in the rollup calculation. This field should contain the values you want to aggregate.
  * Select a rollup function to perform on the values from the linked table.
  * Click **Create** to create a new rollup field.

After configuring these options, the rollup field will calculate the specified value based on the linked table’s data.

To change the field title or link to table field of an existing rollup field, click on the dropdown next to the field and [edit the details](/user-docs/field-customization#edit-field).

![Rollup field in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/64315572-6f87-4c0c-a72b-05d8fc8925ed/Rollup%20field.webp)

## Rollup functions

Rollup functions are calculations that can be performed on the values from the linked table. Baserow provides several functions that can apply, including:

  * `any`: Returns true if any one of the values from the linked rows is true, or false if any one of the values is false. The usable type for this argument is a list of [boolean values](/user-docs/boolean-field) obtained from a lookup.
  * `every`: Returns true if all values from the linked rows are true, or false if all the values are false. The usable type for this argument is a list of [boolean values](/user-docs/boolean-field) obtained from a lookup.
  * `max`: Returns the maximum value from the linked rows. The usable type for this argument is a list of [text](/user-docs/single-line-text-field), or [number](/user-docs/number-field), or char, or [date](/user-docs/date-and-time-fields) values obtained from a lookup.
  * `min`: Returns the minimum value from the linked rows. The usable type for this argument is a list of [text](/user-docs/single-line-text-field), or [number](/user-docs/number-field), or char, or [date](/user-docs/date-and-time-fields) values obtained from a lookup.
  * `count`: Returns the number of items in its first argument.
  * `avg`: Returns the average of all the values from the linked rows. The usable type for this argument is a list of [number](/user-docs/number-field) values obtained from a lookup.
  * `sum`: Returns the sum of all the values from the linked rows. The usable type for this argument is a list of [number](/user-docs/number-field) values obtained from a lookup.
  * `stddev_pop`: Returns the population standard deviation of the values from the linked rows. The population standard deviation should be used when the provided values contain a value for every single piece of data in the population. The usable type for this argument is a list of [number](/user-docs/number-field) values obtained from a lookup.
  * `stddev_sample`: Returns the sample standard deviation of the values from the linked rows. The sample deviation should be used when the provided values are only for a sample or subset of values for an underlying population. The usable type for this argument is a list of [number](/user-docs/number-field) values obtained from a lookup.
  * `variance_pop`: Returns the population variance of the values from the linked rows. The population variance should be used when the provided values contain a value for every single piece of data in the population. The usable type for this argument is a list of [number](/user-docs/number-field) values obtained from a lookup.
  * `variance_sample`: Returns the sample variance of the values from the linked rows. The sample variance should be used when the provided values are only for a sample or subset of values for an underlying population. The usable type for this argument is a list of [number](/user-docs/number-field) values obtained from a lookup.

