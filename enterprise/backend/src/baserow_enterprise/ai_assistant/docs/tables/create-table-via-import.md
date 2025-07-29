# Baserow Documentation

Source: https://baserow.io/user-docs/create-a-table-via-import

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Create a table via import

With Baserow, you can import a file and create a brand-new table within your existing database. In this article, we will explore the various ways you can create a new table in Baserow through importing.

There are multiple ways to create a new Baserow table via import:

  * Paste table data
  * Import a CSV file into a database
  * Import an XML file into a database
  * Import a JSON file into a database

Other ways to create a new Baserow table:

  * [Start with a new table](/user-docs/create-a-table#start-with-a-new-table)
  * [Duplicate an existing table](/user-docs/create-a-table#duplicate-a-table)

> Note that importing a new table into your database is different from importing additional data into an existing table. To import or copy the cells from a spreadsheet and paste the table data, view this article on [how to import a file with tabular data into an existing table](/user-docs/import-data-into-an-existing-table).

## Overview

You can easily import your data from almost anywhere into Baserow from a data file. We’ll get you up and running in no time! The importing feature makes it easy to transfer your data in bulk from another platform.

The following file types are supported when you import a table into your database:

  * Comma-separated values (CSV)
  * Extensible Markup Language (XML)
  * JavaScript Object Notation (JSON)

Once the data file is ready, you can import it into your database.

> Note that you are limited to importing up to a maximum of 5000 rows.

## Paste table data

Baserow has many [supported fields](/user-docs/baserow-field-overview), and each has its own set of formatting rules. Always make sure the data you are importing into Baserow has been formatted properly to get the right content into the right fields.

  1. Within your Database in the sidebar, click **\+ Create table**.
  2. Input a name for the new table.
  3. Select **Paste table data**. You can copy the cells from a spreadsheet and paste them.
  4. If the first row copied is a header, the checkbox is ticked by default.
  5. Click **Add table**.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-15_at_09.25.40.png)

> Want to take your data outside of Baserow? Learn how to [export data out of a Table](/user-docs/export-tables)!

## Import a CSV file into a database

You can import an existing CSV by uploading the .CSV file with tabular data. Most spreadsheet applications will allow you to export your spreadsheet as a .CSV file.

  1. Within your database in the sidebar, click **\+ Create table**.

  2. Input a name for the new table.

  3. Select **Import CSV file**.

  4. Click **Choose CSV file** to browse and upload a file from your computer.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-08_at_23.35.56.png)

  5. Confirm the Column separator and Encoding format from the drop-down menus.

  6. Check **yes** to confirm the first row is a header if you want the top row of your spreadsheet to be included in your import, or unclick to go without a header.

While we recommend you have header rows in your tables, it is not required. If you do include a header row, each column needs a different header. A header row gives your readers a visual reference for each column’s content.

  7. In the preview box, double-check that your data looks good.

  8. Click **Add table**.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-08_at_23.47.13.png)

## Import an XML file into a database

  1. Within your Database in the sidebar, click **\+ Create table**.
  2. Input a name for the new table.
  3. Select **Import an XML file**.
  4. Click **Choose XML file** to browse and upload a file from your computer.
  5. In the preview box, double-check that your data looks good.
  6. Click **Add table**.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/3438ffeffc6aac906ba26b5611f81ff640fe9bce.webp)

## Import a JSON file into a database

You can import an existing JSON file by uploading the .json file with tabular data, i.e.:
    
    
    [
      {
        "to": "Tove",
        "from": "Jani",
        "heading": "Reminder",
        "body": "Don't forget me this weekend!"
      },
      {
        "to": "Bram",
        "from": "Nigel",
        "heading": "Reminder",
        "body": "Don't forget about the export feature this week"
      }
    ]
    

  1. Within your Database in the sidebar, click **\+ Create table**.
  2. Input a name for the new table.
  3. Select **Import a JSON file**.
  4. Click **Choose JSON file** to browse and upload a file from your computer.
  5. Confirm the Encoding format from the drop-down menus.
  6. In the preview box, double-check that your data looks good.
  7. Click the **Add table** button to import the file to Baserow.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-09_at_12.10.35.png)

## Troubleshooting

When you import a file into Baserow, all field values are imported as text. Each cell has a distinct type that may not correspond to a [field type](/user-docs/baserow-field-overview) on import. After the import, you can convert the fields to their equivalent Baserow field types.

Alternatively, to select the field type on import, [import data into an existing table](/user-docs/import-data-into-an-existing-table) with configured field values.

