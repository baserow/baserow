# Baserow Documentation

Source: https://baserow.io/user-docs/import-airtable-to-baserow

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Import Airtable base to Baserow

![Import Airtable base to Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/341f6ab4-3927-45d6-a687-50106ec3f434/Airtable%20import.png)

Baserow allows you to import data as a new database into an existing workspace within minutes.

If you’re familiar with Airtable databases, diving into a new platform can seem daunting. But, there’s no need to be overwhelmed! There are easy ways to transition.

## Prerequisites

You need to retrieve your base share link from Airtable.

  1. In Airtable, click on the Share button in the top right corner after opening your base.
  2. Next, choose the **Base** tab.
  3. Click on the **Share publicly** button in the share modal.
  4. Enable shared base link (read-only) to turn on full base access.
  5. Copy generated shared base URL.

If you’re unable to find it, see [Airtable’s help and support documentation](https://support.airtable.com/docs/creating-a-base-share-link-or-a-view-share-link#basesharelink) for detailed guidelines on creating a base share link or a view share link.

## Create a new database from Airtable import

To import your Airtable base, go to your Workspace

  1. Click the **\+ Create new** button in the workspace you want to add the database to
  2. Select **Database** from the dropdown option
  3. Switch to the **Import from Airtable** tab
  4. Get the shared link to your entire Airtable base.
  5. Copy the shared base public link and paste it into the Baserow input field.
  6. Click **Import from Airtable**.

![Import Airtable base to Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2ae85aff-7424-4f53-ad75-9c839a184360/Screenshot%202023-01-11%20at%2007.32.17.png)

## Data import process

We have extensively tested the import feature with various types of bases and configurations. When you import your data into Baserow, your tables, views, fields, and data will be imported seamlessly. All the rows in your table will be automatically filled with data.

Airtable views combine sorts, filters, hidden columns, and other elements. Most of your data will import successfully, including Grid view features like field arrangements, sorting preferences, grouping settings, filters, and row coloring. Some field types, automations, and features that Baserow doesn’t yet support won’t be imported. You’ll receive a detailed report listing any items that couldn’t be imported, helping you track what’s missing.

There are only minor differences between most of the [field types in Baserow](/user-docs/field-customization) and Airtable. To help you manage these differences, refer to the following table:

Airtable Column Type | Corresponding Baserow Field Type  
---|---  
Single line text | Single line text  
Long text | Long text  
Attachment | File  
Single select | Single select  
Multiple select | Multiple select  
Checkbox | Boolean  
URL | URL  
Date | Date  
Phone number | Phone number  
Email | Email  
Number | Number  
Currency | Number  
Percent | Number  
Duration | Number  
Rating | Rating  
Link to another record | Link to table  
Created time | Created on  
Last modified time | Last modified  
  
Some additional notes on this:

  * The Percentage field type imports as a Number field type with “%” set as a suffix
  * Currencies will be imported as Number fields with their currency symbols set as prefixes
  * Numbers will retain their formatting for decimal places and separators (thousand and decimal), but will not preserve presets or large number abbreviations
  * Dates set to Date (local) and Date (friendly) will be imported as Date ISO
  * Single and Multi-select fields options colors may slightly differ from Airtables

The following Airtable field types will not be imported into Baserow. Before importing the data, you have the option of changing the field type. These fields can be modified in Airtable and imported into Baserow as text or numbers.

  * Formula
  * Lookup
  * Assignee
  * Last modified by
  * Created by
  * Button
  * Barcode
  * Rollup

Additionally to fields, the following items will not be imported:

  * Row comments
  * Row revision history
  * Field descriptions
  * Access control settings

You can also [add a database from a template](/user-docs/add-database-from-template) or [create a database from scratch](/user-docs/create-a-database).

## Related content

  * [How to migrate from Airtable to Baserow](/blog/how-to-migrate-from-airtable-to-baserow)
  * [Databases overview](/user-docs/intro-to-databases)
  * [Create a database](/user-docs/create-a-database)
  * [Add database from template](/user-docs/add-database-from-template)
  * [Delete a database](/user-docs/delete-a-database)

