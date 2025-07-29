# Baserow Documentation

Source: https://baserow.io/user-docs/export-a-view

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Export a view

In this section, you’ll learn how to export views from Baserow.

## Overview

> This option is restricted to the Grid view only.

You can download data from a view by accessing the view menu, and then choosing a specified export format encoding. You can sync and back up your data by exporting it to another database. The export will contain all field values that are present in the view, except the [row comments](/user-docs/navigating-row-configurations).

![Select the Baserow view to export](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/729334bf-e50d-4dd1-a905-6a8459719bb5/Select%20the%20view%20to%20export.webp)

## Supported file formats

Export file formats include:

  * Comma-separated values (CSV),
  * Extensible Markup Language (XML),
  * JavaScript Object Notation (JSON),
  * Excel to download the data in .XLSX format,
  * Export files.

You can [export either an entire table](/user-docs/export-tables) or a specific view. This provides a simple way to convert your data for use in other tools.

![Image: Baserow export to Excel](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/c65f6d43-55ae-45f1-8086-d132f868b6ec/excel_export.webp)

## How to export a view

You can export a table or view. To export a view:

  1. Click on the ellipsis ••• beside the required view you want to export to open your view settings.
  2. Select **Export view**.
  3. Select the view to export from the dropdown menu to export that view.
  4. Choose the file format you would like to export.
  5. When exporting as CSV, you have additional options to select a Column separator and Encoding. The default delimiter to separate values with is a comma `,`. Other delimiters include `;`, `|`, `<tab>`, record separator (30), unit separator (31). 
     * Encoding converts the data into a format that can be supported and used by different systems.
  6. This option will be selected by default if the first row is a header.
  7. Click **Export** and download the file.

After you export the view, the file you download will be found in your device’s default download folder.

Want to bring your existing content into Baserow? Find out how to [import data](/user-docs/intro-to-tables) into a database or table in this support article.

## Related content

  * [Create a view](/user-docs/create-custom-views-of-your-data).
  * [Collaborative views](/user-docs/collaborative-views).
  * [Personal views](/user-docs/personal-views).
  * [View configuration options](/user-docs/view-customization).

