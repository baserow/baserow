# Baserow Documentation

Source: https://baserow.io/user-docs/footer-aggregation

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Field Summary

Field Summaries are used to summarize field values within a [Grid View](/user-docs/guide-to-grid-view). These summaries provide valuable insights into your data at a glance. You can think of Field Summaries as pre-built functions that you can apply to each field.

Field Summaries are contextual to each field type and provide different options for aggregating, calculating, and evaluating field values. These can be sums, averages, or even total values that tell you how many rows are filled or empty.

In Baserow, Field Summaries play a crucial role in computing values derived from a single field in a table. This section covers the process of using Field Summaries in your Baserow database.

## Overview

In Baserow, you can select the Field Summary option in any [Grid View](/user-docs/guide-to-grid-view). The resulting value is displayed at the bottom of its respective field for easy reference.

Note 1: Referencing Field Summary values is not possible. Note 2: Field Summaries do not work for Lookup fields.

![Field Summaries in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/901c4fb0-56f6-4933-b768-5ef6a09446ac/footer%20baserow.webp)

## Get a Field Summary

By default, the Field Summary for each field is empty. To obtain the summary of a specific field, follow these steps:

  1. Navigate to the [Grid View](/user-docs/guide-to-grid-view) you want to work in.
  2. Look for the portion of the screen that contains the number of rows in your view. This is the footer.
  3. Within the footer, hover over and click on any footer cell located beneath the field.
  4. A menu listing available Field Summaries will appear. Select any Field Summary (e.g., Sum, Average, Min, Max, Unique, Percent empty, etc.) to apply it to that particular field.

![Use a Field Summary in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-14_at_20.16.24.png)

Once you’ve chosen a Field Summary, the corresponding value will be displayed in the field’s footer. This value will automatically update whenever the data in the table changes.

## Field Summaries in Public Grid Views

When you [share a Grid View publicly](/user-docs/guide-to-grid-view#share-grid-view), any Field Aggregations you’ve applied will also be visible to your viewers. This helps present summarized information.

Note: Only Field Summaries you have explicitly set will be displayed. There are no Field Summaries applied by default.

![Field Summaries in public Grid Views](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d7d767e6-6285-4a69-b7ab-cc30d2a63ec2/footer%20aggregations%20in%20public%20grid%20views.png)

## Types of options in Field Summaries

The field type will determine the kinds of Field Summaries that are available. Some functions will appear in Date, Single Select, Single Line Text, Phone Number, Email, File, Multiple Select, Formula, Link To Table, Long Text, URL, Created On, and Last Modified By fields. These are:

  * Empty
  * Filled
  * Percent empty
  * Percent filled
  * Unique (except Link to table, file, created on and multiple select fields)

## Options for Date fields

In addition to the general function, certain functions will only appear in Date, Last Modified, and Created On:

  * Earliest date
  * Latest date

![Field Summary options for Date, Last Modified, and Created On fields](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-28_at_21.44.22.png)

## Options for Boolean fields

A Field Summary that’s particular to Boolean fields allows you to see the number or percentage of checked and unchecked cells.

  * Checked
  * Unchecked
  * Percent checked
  * Percent unchecked

![Field Summary options for Boolean fields.](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-28_at_21.48.53.png)

## Options for Number and Rating fields

In addition to the general options available, you can use the Field Summaries in a Number field to calculate a few different values. For the Number and Rating fields, these are the options available:

  * Min
  * Max
  * Sum
  * Average
  * Median
  * Standard deviation
  * Variance

![Field Summaries in a Number and Rating fields](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-28_at_22.05.44.png)

## Related content

  * [Work with Grid Views](/user-docs/guide-to-grid-view).
  * [Create a field](/user-docs/adding-a-field).
  * [Field configuration options](/user-docs/field-customization).

