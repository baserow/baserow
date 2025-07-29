# Baserow Documentation

Source: https://baserow.io/user-docs/count-field

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Count field

A count field lets you see how many rows are linked to a particular row in your database. This is helpful to keep track of statistics.

This support article provides an overview of the count field and how to configure it in your table.

## Using the count field

Count fields are read-only fields that make it easy to perform calculations on data from related tables. Once the count field is configured, you can use it to gain insights into the number of linked records in your table.

The count field will display the total number of linked records for each individual row, providing you with a quick summary of the associated data.

You can [sort](/user-docs/field-customization#sort-fields) or [filter](/user-docs/field-customization#create-a-filter) the table based on the count field to focus on specific records with a certain number of linked records.

## Create a count field

> The count field can only be used when you have a [link to table](/user-docs/link-to-table-field) field in your table. To use a count field, create a link to table field that’s linked to another table in your database.

To add a count field,

  * Within your database, select the table where you want to add the count field.
  * Click on the **+** button located on the far-right side of the table to [create a new field](/user-docs/adding-a-field).
  * Input the name of the field.
  * In the field options, choose “Count” from the list of field types.
  * In the configuration panel, select the link to table field from which you want to count linked rows. 

> If you have multiple link to table fields, select which field on the table is linked to the rows you want to count.

  * Click **Create**.

![Baserow count field](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/1cddd056-3354-44d6-9a5b-95e6115d41ae/Count%20field%20Baserow.webp)

After configuring these options, the count field will automatically update to display the number of linked records in each row.

To change the field title or link to table field of an existing count field, click on the dropdown next to the field and [edit the details](/user-docs/field-customization#edit-field).

