# Baserow Documentation

Source: https://baserow.io/user-docs/import-data-into-an-existing-table

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Import data into an existing table

Importing your data can be useful for taking action in Baserow. By understanding the different fields that can be imported, you gain valuable context to make the most of your data. [Learn more about fields in Baserow](/user-docs/baserow-field-overview).

This article will cover the step-by-step process to effortlessly import data into an existing table.

## Overview

You can import a CSV file, a JSON file, or an XML file with tabular data, or copy the cells from a spreadsheet and paste the table data.

> Note that importing additional data into an existing table is different from importing a new table into your database. To create a new table from import, view this article on [how to import a CSV file, a JSON file, or an XML file with tabular data into a database](/user-docs/create-a-table#add-a-new-table-via-import-to-database).

For other ways to create a Baserow table, please see these articles:

  * [Start with a new table](/user-docs/create-a-table#start-with-a-new-table)
  * [Duplicate an existing table](/user-docs/create-a-table#duplicate-a-table)
  * [Paste table data](/user-docs/create-a-table-via-import#paste-table-data)
  * [Create a new table from an import](/user-docs/create-a-table-via-import).

## Import additional data into existing tables

To import a file into an existing table, open the table where you want to import your data.

  1. Click on the ellipsis ••• beside a view to open your view settings.
  2. Select **Import file**.
  3. Select the file type you would like to import and click **Import**.
  4. To update existing records with imported data when matches are found, put a checkmark next to the option “Update rows if they already exist.” If not checked, all rows will be imported as new records, regardless of potential duplicates.

The columns of the Baserow fields will be automatically mapped to the correct fields in your table. You can change the mapping by choosing the desired target field, or use the mapping to manually set up the logic of which fields to merge and where. Any incompatible cell will remain empty after the import.

To update existing records, put a checkmark next to the option “Update rows if they already exist.”

> Tip 💡 Toggle between the Import Preview and File Content preview to compare the logic of which fields to merge and where.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/01bc77ac-38af-4150-92ed-42fb7353468f/20960a7acf0da910a21d42c8d33a204e699d6a7f.webp)

The file importer can import to [link row](/user-docs/link-to-table-field), [single select](/user-docs/single-select-field) and [multiple select](/user-docs/multiple-select-field) columns and automatically set them up with links or options.

