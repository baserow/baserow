# Baserow Documentation

Source: https://baserow.io/user-docs/paste-data-into-baserow-table

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Paste data into cells

Baserow is configured to automatically create rows when pasting more [rows](/user-docs/overview-of-rows) than available. There is no need to enable this feature separately; it is built-in and ready to use.

This guide explains how to paste data into cells in a Baserow table.

## Overview

When you paste data into a table in Baserow and the number of rows you are pasting exceeds the current number of rows in the table, Baserow will automatically create the additional rows for you. For example, if you want to paste 10 rows of data into a table that only has 6 rows, Baserow will create the additional 4 rows to accommodate the pasted data.

## How to create rows by pasting data

To automatically create rows when pasting more rows of data than are available in your table,

  * Open your desired table in Baserow.
  * Select the area where you want to copy your data. Make sure the copied data corresponds with the [field types](/user-docs/baserow-field-overview) in the table you want to paste.
  * Right-click within the selected area and choose the “Copy cells” option to copy the data you wish to paste. Alternatively, you can use the [keyboard shortcut](/user-docs/baserow-keyboard-shortcuts) (`Ctrl` \+ `C` on Windows, `Command` \+ `C` on Mac) to copy the data.
  * Use the [keyboard shortcut](/user-docs/baserow-keyboard-shortcuts) (`Ctrl` \+ `V` on Windows, `Command` \+ `V` on Mac) to paste the data on an existing row.

![Paste data in Baserow to create new row](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/48479958-51a3-4f56-b5d9-e20fa14f629b/Paste%20data.webp)

> If you have any existing data in the rows where you are pasting new data, Baserow will overwrite the existing data with the pasted data. Make sure to double-check and review the data before pasting to avoid unintentional data loss.

Baserow will automatically create the required number of rows to accommodate the pasted data. The newly created rows will contain the pasted information.

## Filling multiple cells with the same value

When you copy a cell containing data and then select multiple cells to paste into, the copied value will be pasted into each of the selected cells.

For example, if you copy a cell containing the number “10” and select five empty cells to paste into all five cells will now display the value “10”.

![Paste a single value into Baserow selected cells](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/addca178-58ea-408e-843d-5866a445e681/Paste%20a%20single%20value%20into%20all%20selected%20cells.png)

