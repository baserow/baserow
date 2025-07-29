# Baserow Documentation

Source: https://baserow.io/user-docs/lookup-field

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Lookup field

The Lookup field is used to cross-reference data that is kept in different tables. The Lookup field enables users to connect rows from different tables within a single database. With Lookup fields, users can easily reference data from one table to another, eliminating the need for repetitive data entry and reducing the chances of errors.

In this section, we will take a closer look at the Baserow Lookup field and explore its various use cases and benefits.

![Using a lookup field in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/5b260e48-458f-46f0-9094-94c6a53a09b9/Screenshot_2022-07-15_at_19.55.19.png)

## Using a lookup field

Lookup fields are read-only fields. When creating a lookup field you can choose a ‘Link to table’ field in the same table and a field in the related table.

A lookup field allows you to look up a specific field in a linked row. Lookup can only be used when you have a [link to table field](/user-docs/link-to-table-field) in your table. You can copy row contents from one linked table into another linked table using a lookup field to establish relationships between two different tables.

For every relationship in the Link to table field, it shows the corresponding cell value of the related row. You can add or remove relationships via the “Link to table” field and this will automatically update the lookup field cell value. If you want to update the value, you need to find the related row and update the cell related to the chosen field in the lookup field.

A classic example of retrieving data from another table would be an Orders database. If on one table, the customer number is the identifying field for who made the order, other information about the customer, like name, address, telephone number, etc. can be collected from a customer database.

The data is easily retrieved by looking for the customer ID within the customer table and then retrieving the right information and populating the order table with the correct information. This is another way that time can be saved when you’re creating a database. This can also create table relationships that make databases more dynamic and useful.

## Create a lookup field

Start by creating a link to table field before using a lookup field.

To create a lookup field,

  1. Click the plus sign + to the right of your existing fields or [insert a new field](/user-docs/field-customization) next to an existing field.
  2. Select the lookup field type and input the name of the field.
  3. Select a link row field and a field to lookup.
  4. Click **Create**.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2d7af812-dd05-4876-a51c-c6aad194b590/Screenshot_2022-07-14_at_07.36.11.png)

If you have multiple link to table fields, you will be given the choice of which link to table field to use for the lookup. Choose the field from those linked rows that you want to display after making that choice.

To change the field title, link row field, or field to lookup in an existing lookup field, click on the dropdown next to the field and modify the details.

## Sort by a lookup field

You can sort the Lookup field type according to the looked up values from the linked table. All field types that can be looked up can be sorted, except [formulas](/user-docs/understanding-formulas) that result in a URL link using the `button` or `link` formula functions and `date_interval` formulas.

Fields can be sorted in ascending order (A → Z (or) 1 → 9 (or) ☑︎ → ☐) or descending order (Z → A (or) 9 → 1 (or) ☐ → ☑︎). Keep in mind that while sorting in ascending order, blank values nearly always appear at the top.

![Sort by lookup field](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/1a46757f-fa38-4aab-917a-48df5fb31002/Sort%20by%20lookup%20field.png)

## Filter by a lookup field

You can filter a Lookup field type according to the values from the linked table. Not all field types can be filtered within a Lookup field. Currently you are not able to filter by the Duration field type.

