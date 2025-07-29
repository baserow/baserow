# Baserow Documentation

Source: https://baserow.io/user-docs/overview-of-rows

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Rows overview

A row is essentially a record or entry in a table. Rows in Baserow can contain various types of data, such as text, numbers, dates, attachments, and even links to other records in the same or different tables. Each row can also be assigned a unique identifier or [row ID](/user-docs/overview-of-rows#what-is-a-row-identifier), which can be used for reference and sorting purposes.

In this section, we will cover the concepts related to Rows in a table.

## What is row in Baserow?

Each default table in Baserow is organized into a grid of rows, fields (columns), and cells. Columns and rows are used to display data in a table. All the data in the table that is relevant to a data type is organised into rows.

A row is a horizontal grouping of data while a column contains vertically-aligned cells. In a row, the data is read from left to right, while in a column, the data is read from top to bottom.

In the screenshot below, every row within the “All Interviews” table is in the database "Applicant Tracker.”

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-14_at_20.23.05.png)

## What is cell in Baserow?

A cell is the intersection of a row and a column. The data is stored in the cell. In the screenshot below, the cell containing “Valery Dugall” is in row 7.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-08_at_10.36.19.png)

In further sections, you’ll find everything you need to get started. You don’t have to worry about learning all about Baserow on your own: we put together some tips to help you grow familiar with the platform quickly.

## What is a row identifier?

A Row ID is a number that uniquely identifies that row of data. Note that, the row ID is not intended to count the number of rows in a table. When a row is deleted, the rows that remain are not renumbered. The assigned number is permanently attached to a row and cannot be changed or deleted, even after the row is deleted. The numbering may then have gaps as a result.

> Use the `row_id()` [formula](/user-docs/understanding-formulas) to return the row’s unique identifying number.

## What is a row count?

A row count automatically generates a unique, automatically incremented number for each record. You can switch between the row numerical count and row identifier by clicking the field header. By switching to row count, you can see numbering without gaps.

![What is a Row Identifier and Count](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/0d002039fbd46687b129f79701286b2313493502.webp)

## Troubleshooting

### I cannot select more than 200 rows in a table.

Multi-selecting rows are limited to 200 selections at a time. You can only select a maximum of 200 rows at a time because Baserow lazy loads only 200 rows at a time. This is so you can easily scroll through millions of rows without having to download them all.

