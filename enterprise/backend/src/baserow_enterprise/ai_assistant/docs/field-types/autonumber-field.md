# Baserow Documentation

Source: https://baserow.io/user-docs/autonumber-field

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Autonumber field

The Autonumber field automatically generates unique and incremented numbers for each row. This field is often used as a primary key to uniquely identify each entry in a table.

## Overview

The Autonumber field in Baserow automatically assigns a unique number to each new row. Numbers are assigned in ascending order based on the row’s [creation date and time](/user-docs/date-and-time-fields).

Users cannot manually change the autonumber values, ensuring data integrity. It works seamlessly within formulas to reference row numbers or create calculated fields.

![Autonumber field in  Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/f71bc95d-9ce9-49fa-8a6c-92d023d1968b/Autonumber.png)

## Add an autonumber field

To add an autonumber field,

  1. Click the plus sign `+` to the right of your existing fields.
  2. Select the Autonumber type and name the field. You can add a unique field name in the customization menu.
  3. Click **Create**.

## Re-number an autonumber field

Autonumbering always begins with 1. Sorting rows doesn’t affect the autonumber sequence.

Deleting rows creates gaps in the sequence, which are not automatically renumbered.

To re-number rows:

  1. Delete and recreate the autonumber field.
  2. Convert the field to a different type and back to autonumber.

## Related content

  * [Field overview](/user-docs/baserow-field-overview)
  * [Create a field](/user-docs/adding-a-field)
  * [Field configuration options](/user-docs/field-customization)
  * [Working with timezones](/user-docs/working-with-timezones)
  * [Date and Time Fields](/user-docs/date-and-time-fields)

