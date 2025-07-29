# Baserow Documentation

Source: https://baserow.io/user-docs/primary-field

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Primary field

By default, the primary field is the first field in a table. Every row in your table should be identified by a unique name. The primary field may be used as a row description in other areas of the UI. For example, when you [link a row](/user-docs/link-to-table-field) to another table, the title card representing the linked row displays the value of the primary field.

The position of the primary key field in a table as the first column is fixed and cannot be changed.

![Copy primary field data in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/eb23db1a-13f3-43a1-bf7d-a44d468ecd67/Screenshot_2022-07-12_at_11.47.04.png)

## Configure the primary field

While you cannot remove the primary field, you have options to customize it. You can change the type of data it stores, duplicate its information into another field, or select a different field to serve as the primary field.

To customize the primary field, click on the arrow next to the field name and select an option to edit the field name and type, create a filter, or sort rows by the primary field.

The Primary field type supports these customization options:

  * [Field editing](/user-docs/field-customization#edit-field)
  * [Duplicating a field](/user-docs/adding-a-field#duplicate-an-existing-field)
  * [Sorting by a field](/user-docs/field-customization#sort-fields)
  * [Filtering by a field](/user-docs/field-customization#create-a-filter)

![!Screenshot 2022-07-13 at 17.00.20.png\(Primary%20Field%2021c4230ce41445b19ee23df0f74ec0c3/Screenshot_2022-07-13_at_17.00.20.png\)](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b0d7c9ee-5f06-467a-b066-9d323de83ce1/Screenshot_2022-07-13_at_17.00.20.png)

## Change the primary field

> Changing the primary field can affect [data relationships](/user-docs/link-to-table-field). It’s recommended to carefully consider the implications before making changes.

There are two ways to change your primary field:

Method 1: Using field options

  1. Click the arrow next to the primary field name.
  2. Select “Change primary field”.
  3. Choose the new field you want to use as the primary field.

![Change primary field in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9abf02f1-4aa9-4c7b-bb61-8b30f36194d4/primary%20field.jpg)

Method 2: Copying and pasting data

  1. [Create a new field](/user-docs/field-customization) to hold the values of your current primary field. For consistency, ensure the new field has the same data type as the primary field.
  2. Select the data in your current primary field.
  3. Copy the selected data (`Ctrl+C` or `Cmd+C`).
  4. Paste the copied data into the new field (`Ctrl+V` or `Cmd+V`).
  5. Change the field type, if required, and populate the pimary field.

![!Screenshot 2022-07-12 at 11.39.43.png\(Primary%20Field%2021c4230ce41445b19ee23df0f74ec0c3/Screenshot_2022-07-12_at_11.39.43.png\)](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/568751c8-ebf6-42c4-af27-bf5ffa74580f/Screenshot_2022-07-12_at_11.39.43.png)

## Change the field type

If you’d like to change your primary field name or the default single line text type to a different field type,

  1. Click on the arrow next to the primary field name.
  2. Select **Edit field**.
  3. Designate a new field type for your primary field.

> The primary field supports all other field types, except the [link to table field](/user-docs/link-to-table-field).

![Change the primary field type in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/342cf938-7f65-4e2c-8d37-4356ac09c2cc/Screenshot_2022-07-12_at_11.57.34.png)

## Supported field types

Each row’s primary field acts as its unique identifier, and cannot be deleted, moved or hidden. The primary field is a text-based field by default. It supports all other field types, except the [link to table field](/user-docs/link-to-table-field).

Baserow currently allows for the following field types to be used as primary fields:

  * Single line text
  * Long text
  * Number
  * Rating
  * Boolean
  * Date
  * Last modified
  * Created on
  * URL
  * Email
  * File
  * Single select
  * Multiple select
  * Phone number
  * Formula
  * Lookup

![Primary Field in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/3e44b0e0-1772-4cb4-8a14-81fced8e8e3d/Screenshot%202023-03-09%20at%2012.19.54.png)

