# Baserow Documentation

Source: https://baserow.io/user-docs/field-customization

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Field configuration options

You can customize the field (column) type and access additional options from the field’s dropdown menu after you’ve created it. This support article will cover the various options for customizing fields. For an overview of field types supported in Baserow, refer to this [article on Baserow fields overview](/user-docs/baserow-field-overview).

## Field configuration menu

Click the dropdown arrow next to the name of the field you want to edit to open the field configuration menu.

![Field configuration menu](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/89263b61-677b-441c-b8ea-9b246d9a2e10/Screenshot%202023-03-09%20at%2009.33.00.png)

Different [field types](/user-docs/baserow-field-overview) have different customization options. The following options are covered:

  * [Field editing](/user-docs/field-customization#edit-field)
  * [Inserting a new field](/user-docs/adding-a-field#insert-a-new-field)
  * [Duplicating a field](/user-docs/adding-a-field#duplicate-an-existing-field)
  * [Sorting by a field](/user-docs/field-customization#sort-fields)
  * [Filtering by a field](/user-docs/field-customization#create-a-filter)
  * [Hiding fields and field visibility](/user-docs/field-customization#hide-field)
  * [Deleting a field](/user-docs/field-customization#delete-field)
  * [Adjust the width of a field](/user-docs/guide-to-grid-view#adjust-the-width-of-a-field)

> Only a few field configuration options are available for the primary field. Please [refer to this article](/user-docs/primary-field) for more details on customizing the primary field.

## Reorder fields

You can rearrange the order of the fields in your grid view by clicking and dragging the field header to move the fields.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d4629b8a9716dfd0131a55493bfb263c28fbb669.webp)

You can also easily move a field directly by clicking and dragging a field in the [enlarged view](/user-docs/enlarging-rows).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/0b7a08e3ed96acd2eb4f7be1c918788fda73d151.webp)

You can select a field and either [insert a new field](/user-docs/adding-a-field) to the left or right of that field.

## Edit field

To edit a field,

  1. Click on the dropdown icon next to the field you want to edit.
  2. Select **Edit field**.
  3. Click the **Change** button when all desired changes are made.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/21050e78aa6f439f8468e5b1093c6c6254fbedb6.webp)

> Although you cannot delete the [Primary field](/user-docs/primary-field), you can change its type, copy the data to another field, or make a different field as the Primary field.

### Change an existing field type

You can create a new field using the values from an existing field. From the field customization menu, select a new field from the dropdown. This will convert the values in your existing field to the new field format.

When you convert an existing field with existing cell values to a new field type, Baserow does its best to convert the current cell values to the new type. For example, a single line text field can be changed into a long text field. However, keep in mind that with particular kinds, some conversions might not be possible. For example, changing a text field to an attachment field will remove all of the text values.

You can undo your edit and restore the field to its previous state if you discover that you lost some cell values during the conversion by using the [keyboard shortcut](/user-docs/baserow-keyboard-shortcuts) `Ctrl Z` to [restore the data that was lost](/user-docs/data-recovery-and-deletion) due to the conversion.

## Sort fields

> Note that you cannot sort by [File](/user-docs/file-field) and [Link to table](/user-docs/link-to-table-field) fields.

There are numerous ways to arrange distinct field types. This allows you to easily organize and arrange your data in the desired order. Baserow supports sorting on the [Grid View](/user-docs/guide-to-grid-view) and Gallery View. Other view types have their default sorting. A Calendar View is automatically sorted by date and a Kanban View is sorted by a single select field.

Fields can be sorted in ascending order (A → Z (or) 1 → 9 (or) ☑︎ → ☐) or descending order (Z → A (or) 9 → 1 (or) ☐ → ☑︎). Note that while sorting in ascending order, blank values nearly always appear at the top.

Text field types can be sorted alphabetically (A → Z) or in reverse alphabetical order (Z → A), including single line text, long text, email, multiple select, formula, and URL.

Single-select field values can be sorted alphabetically (A → Z), reverse alphabetically (Z → A), or by First → Last or Last → First option order.

Both ascending order 1 → 9 and descending order 9 → 1 can be used in numerical fields like number, rating, phone number, last modified, created on, and date fields (from the earliest date to the latest date, or from the latest date to the earliest date).

You can either ☑︎ → ☐ in ascending order or ☐ → ☑︎ in descending order sort [boolean fields](/user-docs/boolean-field) according to whether the box has been checked or not.

You can sort the Lookup field type according to the looked up values from the linked table.

> To sort by a [Link to table field](/user-docs/link-to-table-field) in Baserow, you can create a Lookup field that references the [Link to table field](/user-docs/link-to-table-field), and then sort the rows based on the [Lookup field](/user-docs/lookup-field).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-07-01_at_11.51.45.png)

## Create a filter

You can create and combine conditions to customize how rows are filtered, enabling you to build highly specific, organized views for your workflows.

To create a filter,

  1. Click on the dropdown icon next to the field you want to filter by.
  2. Select **Create filter**.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/6469175843f6831a37655e298bb7b805c3c8cd6a.webp)

We advise reading this section on [adding filters in a view](/user-docs/view-customization) first if you are new to creating conditions to filter your rows.

## Group by field

The Group by feature can be found in the [Grid View](/user-docs/guide-to-grid-view). Grouping rows lets you sort your data based on one or more fields. You can add many fields to make subgroups within each group of rows. This allows for better sorting. Plus, you can see how many items are in each group.

Learn more about [group by](/user-docs/group-rows-in-baserow).

![Group by field](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/0c2fa1f3-3a86-4231-b611-3005c98f944f/group%20by%20baserow.png)

## Hide field

To hide or show fields, click the **Hide fields** button in the grid view or the **Customize cards** button in the Kanban view to bring up the hide fields dialog.

> Note that you cannot hide the [Primary field](/user-docs/primary-field).

### Hiding fields from the field header

By clicking the field header in [grid view](/user-docs/guide-to-grid-view) and choosing the **Hide field** option from the dropdown menu, you can also hide a field.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-28_at_14.04.16.png)

### Hiding fields in an expanded row

You also can hide or show specific fields within an [expanded row](/user-docs/enlarging-rows) by clicking the option menu beside the field.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-28_at_14.00.29.png)

## Delete field

> Note that you cannot delete the [Primary field](/user-docs/primary-field).

To delete a field, other than the primary field, you can do it by selecting the ‘Delete field’ option from the dialog box beside the field’s name.

  1. Click on the dropdown icon next to the field you want to delete.
  2. Select **Delete field**.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-28_at_14.12.13.png)

You can recover deleted things by using the **Trash**. To review and restore any fields that have been deleted in a base during the last three days. Learn more on [how to access the trash](/user-docs/data-recovery-and-deletion) here.

## Related content

  * [Field overview](/user-docs/baserow-field-overview)
  * [Add a new field](/user-docs/adding-a-field)
  * [Working with timezones](/user-docs/working-with-timezones)
  * [Formula field overview](/user-docs/formula-field-overview)

