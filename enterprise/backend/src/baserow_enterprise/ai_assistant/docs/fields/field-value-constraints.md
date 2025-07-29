# Baserow Documentation

Source: https://baserow.io/user-docs/field-value-constraints

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Field value constraints

![Field value constraints](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/550ddde3-1604-4aa8-962e-b948a173d8c3/Field%20constraints.png)

Take control of your data quality with our new field value constraint feature. This powerful addition allows you to define specific rules that data must meet before being saved, ensuring consistency across your database.

## What are field value constraints?

Field value constraints let you enforce rules on the values entered into a field. Currently, you can enforce **unique values** , including empty ones. This prevents duplicate data entry at the source, reducing cleanup efforts and maintaining higher data integrity throughout your datasets.

## How to set up a field value constraint

  1. Go to the field you want to constrain.
  2. Click on **Edit field**.
  3. Navigate to the **Advanced** tab.
  4. Select the rule that field values must follow (currently, this is the unique values enforcement).

## Future improvements

In upcoming releases, we plan to introduce more validation rules such as:

  * Numeric range limitations (minimum and maximum bounds)

  * Text length character limits

  * Additional validation rules to give you even more control over your data quality

