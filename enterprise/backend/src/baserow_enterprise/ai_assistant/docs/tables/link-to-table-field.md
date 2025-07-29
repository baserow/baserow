# Baserow Documentation

Source: https://baserow.io/user-docs/link-to-table-field

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Link to table field

Baserow’s Link to table field is a feature for creating relationships between tables and organizing your data in Baserow.

## Overview

The Link to table field is useful for connecting one row in a table to another row in a different table. This can be helpful when you have related data that you want to keep organized and connected.

For example, let’s say you have a database of customers and a database of orders. You could use the Link to table field in the orders table to link each order to the customer who placed it. This would allow you to easily view all orders placed by a particular customer, or view all customers who have placed orders.

> Note that a Link to table field cannot be the primary field of a table.

## Connecting data across tables with linked rows

You can establish connections between tables using the link to table field in Baserow. By linking rows in these tables, you can capture the dynamic relationships between them.

When you begin to build relationships between data in your tables, it’s important to have defined the structure of your data beforehand. This is especially useful if you have many tables containing related data. For example, if you have a table of applicants and a table of roles, you can use a Link to table field to link each applicant to what role will be interviewing for.

> To sort by a Link to table field in Baserow, you can create a Lookup field that references the Link to table field, and then sort the rows based on the Lookup field. This allows you to easily organize and arrange your data in the desired order.

![Connecting data across tables with linked rows in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2f1f564b-242e-4d3a-8d0b-e773e60314ce/Screenshot_2022-07-14_at_07.20.03.png)

## Create a link between two existing tables

You can create links between related rows in a link to table field to represent the relationships between them.

Linked rows allow you to create relationships between your data to minimize redundant rows while ensuring they are available where you need them.

  1. In either related table, create a link to table field to connect both tables by clicking on the `+`.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/10ad1d0f-e256-4c16-adf1-1a89b1701ce0/Screenshot_2022-07-15_at_18.53.51.png)

  2. Click on the dropdown under ‘Select a table to link to’. This will display the linked tables for you to choose from. Individual rows can be linked to one another to establish a relationship between them. You can link two different tables together, and also link to the same table. To create a link that references rows in its own table, you need to create a link to table field and choose the same table as its source.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/19ca35b2-aa33-4e32-ace1-0e5a5fc87d67/Screenshot_2022-07-15_at_18.58.43.png)

  3. Click the Plus `+` button inside a cell in a grid view to open the row select modal.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b496d592-43c6-4210-a73e-2c96c1215429/Screenshot_2022-07-15_at_19.23.52.png)

  4. When viewing from an enlarged view, click the **\+ Add another link** button to open the row select modal, you’ll see a list of rows that you can link to.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/dd8867c7-dc81-4b8b-be0e-d4cffd0b9a1c/Screenshot_2022-07-15_at_19.26.37.png)

  5. If the linked table contains more than 10 rows, you can use the navigation arrows to see all of the rows or search the list to find the desired rows more quickly.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/04d8d01a-9622-41b1-bb79-c69471eee2d5/Screenshot_2022-07-15_at_19.30.26.png)

Once you have added the link to table field, every time you connect two tables using the link to table field, you can see linked information in each table so you’ll know which items are connected to each other. The list of linked rows can have more than one rows selected, one at a time.

## Link field one-to-one relationships

You can now limit link fields to only allow one-to-one relationships between tables. This update gives you better control over data relationships and prevents accidental multiple links when your data model requires one-to-one connections.

Configure this setting in the link field’s properties when creating or editing a link-to-table field by unchecking the **Allow multiple selection** box.

## Create a new row from the row select modal

The row select modal allows multiple row selection, keyboard navigation, and instant search-as-you-type functionality. These allow you to quickly select linked rows, boosting productivity and saving your time.

![Baserow Improved row select modal](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/48140c87-c4a5-44fb-893f-e8b42005cd4f/improved_row_select_modal.webp)

You can create a new row directly from the row select modal. To do this, click the `+` button while choosing a relationship in the link to table field.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/3a18a71a-9b51-4c2f-8167-de6017bac007/Untitled\(26\).png)

Within the row select modal, you can adjust the field’s width, hide fields, and customize the order of the fields in the “Hide fields” menu.

![Image: Baserow row select modal](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b5680ce5-2dc0-4dab-8d95-421c4e843c06/row_select_modal_improvements.webp)

## Unlink a linked row

To unlink a row, select a cell in a link to table field, then click the `X` on the connected row you wish to unlink.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/c631f5ea-4700-4fc2-ab23-26130dd6bf7c/Screenshot_2022-07-15_at_19.33.34.png)

## Enlarge a linked row

If you click on a linked row within a link to table field, an [enlarged version of the row](/user-docs/enlarging-rows) being linked to will open.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/11a315d8-f936-4496-9b3e-b680e4b9c72a/Screenshot_2022-07-15_at_19.42.31.png)

When you click on a linked row within an enlarged row, it will open a new enlarged row above the existing one.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9bd87f4c-afab-4359-b60b-02e91ef5df23/Screenshot_2022-07-15_at_19.45.57.png)

## Change an existing field into a link to table field

You can create a linked row from an existing field using the field customization option. However note that this will delete the values in your existing field, and you will be able to link rows for each value.

Make sure to copy and paste the data into a new field before converting any fields. Next, choose the **Edit field** option from the field customization menu. Select Link to table field, then select the table you want to link rows from.

## Limit selection to view

This allows you to control which rows users can select when working with linked tables. By restricting selection to a [specific view](/user-docs/overview-of-baserow-views), you ensure users can only choose relevant data.

To limit selection to a view,

  * Identify the linked table field: Locate the field in your current table that links to the desired table.
  * Open field settings: Click on the linked table field to access its [configuration options](/user-docs/field-customization).
  * Within the field settings, locate the option labeled “Limit selection to view”.
  * Select the desired view: Click on the dropdown and choose the specific view that should be used for selecting rows in the linked table.

Once you’ve chosen the view, confirm your selection to finalize the configuration.

![Baserow limit selection to view](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/e7cedf1f-d0e6-4291-96e7-8eaa05e05a1f/Link%20to%20table%20field%20limit%20selection.png)

**Note:** By default, views now display a maximum of 20 linked items. If you need to access more than 20 linked items, use the search functionality within the row select modal to find the specific items you need, or adjust the view settings of the linked table to filter the results.

