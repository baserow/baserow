# Baserow Documentation

Source: https://baserow.io/user-docs/formula-field-overview

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Formula field overview

The formula field is available for all Baserow plan types. Formulas can be very helpful in supercharging your database when combined with [other field types](/user-docs/field-customization).

Formula fields in Baserow allow you to perform calculations, manipulate text, and combine data from different fields to derive new insights or automate processes. This guide will walk you through the steps of using formula fields to simplify data calculations and manipulate text effectively in Baserow.

## Differentiating between formulas, functions, and expressions

Formulas, functions, and expressions are fundamental concepts in data management and analysis.

**Formula** : A formula is a set of instructions used to perform calculations, manipulate text, or evaluate conditions based on data. It typically consists of functions, operators, and references to data fields.

Example: In a “Total Price” field, the formula could be: `field('Current Quantity') * field('Cost')`. This formula calculates the total price by multiplying the unit price by the quantity.

**Function** : A function is a predefined operation that takes one or more inputs, performs a specific task, and produces an output. Functions can be mathematical, logical, text-related, or date/time-related, among others.

Example: In the formula `length(field('Product Name'))`, the `length()` function calculates the length of a text string.

**Expression** : An expression is a combination of values, operators, and functions that evaluates to a single value. Expressions are often used within formulas to define calculations or conditions.

Example: In the expression `field('Current Quantity') * field('Cost')`, both `field('Cost')` and `field('Current Quantity')` are field references, and * is the multiplication operator. This expression calculates the total price.

## Using Formula fields in Baserow

Any field on the table can be used as a reference in a formula that refers to another field. Using formulas, you can generate an array of data in each row, including numbers, dates, strings, and more, based on either static or dynamic data from other cells in the same row.

  1. Open your Baserow database and navigate to the table where you want to create a formula field.
  2. Click on the **\+ Add a field** button to add a new field.
  3. Choose **Formula** as the field type. A formula editor will appear.
  4. In the formula editor, you can use mathematical [operators, functions, and references](/user-docs/understanding-formulas) in other fields to build your formula.
  5. Test the formula with different sample data to ensure it produces the desired outcome. Save the formula field once you are satisfied with the formula.

Formulas can reference fields within the same table or even from [linked tables](/user-docs/link-to-table-field).

![what Baserow formulas are](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/388a23b3-06cb-48e1-8fe5-a7efb24d642f/Screenshot%202023-03-09%20at%2008.55.11.png)

## Baserow formula field basics

The first step to using formula fields effectively is to identify your goal or objective. Once you know what you want to achieve, you can then determine the calculation or manipulation you need to perform.

You can utilize Baserow [functions, operators, and references](/user-docs/understanding-formulas) to easily perform calculations like adding up numbers, calculating averages, finding the highest or lowest values, or manipulating text. With these functions, you can also merge fields, extract specific characters, or format text according to your needs.

Functions like `SUM()`, `IF()`, `CONCAT()`, and `DATETIME_FORMAT()` can be helpful. Operators such as `+`, `=`, `<=`, `AND`, `OR`, and `NOT` are also available. Refer to fields using `field('field_name')`.

## Troubleshooting

### Why can’t I change the value of a formula field cell?

You cannot change the value of a formula field cell. This is because a formula field has one formula for the entire field which is used to calculate the individual cells’ values. Try converting the formula field back to a normal field if you are done with your calculation and now want to make specific edits to the results.

### What happens when I delete a field referenced by a formula field?

If you reference a field in a formula, if you then delete the referenced field, your formula field will become invalid and an error will be shown. To fix this you can either restore the deleted field, create a new field with the same name, change the formula to no longer reference the deleted field, or rename another field.

## Related content

  * [Understand Baserow formulas and how to use formulas](/docs/tutorials/understanding-baserow-formulas).
  * [Formula field reference](/user-docs/understanding-formulas).
  * [Technical understanding of how Baserow formulas are implemented](/docs/technical/formula-technical-guide).
  * [Generate formulas with Baserow AI](/user-docs/generate-formulas-with-baserow-ai)

