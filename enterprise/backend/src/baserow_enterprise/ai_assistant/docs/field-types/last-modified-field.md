# Baserow Documentation

Source: https://baserow.io/user-docs/last-modified-field

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Last modified field

The last modified field will always be the most recent date and time that a row was edited by a user. The computed field automatically returns the date and time of the last modification.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/747f0d89-5d87-4948-a067-bafbacd176fc/Screenshot_2022-07-14_at_08.20.59.png)

In this section, we will explore the last modified field in Baserow.

## Overview

When a new blank row is created, the _last modified_ field type will be the same values, until a user makes a change.

A row’s last modified field value never rolls back in time. If you alter a cell and then undo that modification, a row’s last modified field will reflect the time that the undo action was carried out rather than the value of the last modified date that was there before completing the action that was undone.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/4cef1844-f11c-456c-a062-27732e4fbf52/Screenshot_2022-07-14_at_07.44.47.png)

## Add a last modified field

To add a last modified field,

  1. Click the plus sign + to the right of your existing fields.
  2. Select the last modified type and name the field.
  3. Click **Create**

## Track the last modified date and time on computed fields

You can choose to restrict the field so that it only displays the most recent time a particular field was modified. The [date functions in formulas](/user-docs/understanding-formulas) can also be used to return the date and time of the most recent user modification. Using the date functions in formulas, you can specify one or more field names to track modification and return the date and time of the most recent change made to any of the specified fields.

Both the formula function and the last modified field type reflect recent changes to editable fields by a user. They do not capture changes made automatically in any fields, such as formula fields, where the user does not directly modify the cell values but rather uses Baserow to compute the values.

If you add or remove a row from a [link to table field](/user-docs/link-to-table-field), the last modified data will change. However, if the data linked to the [link to table](/user-docs/link-to-table-field) field change, the latest modified time will not change. Although the connected row’s values in the other table have changed, you haven’t altered which row you are linking to. Changing the [link to table](/user-docs/link-to-table-field) row’s fields that are stored in a different table won’t affect the last modified value.

