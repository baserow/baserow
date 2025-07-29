# Baserow Documentation

Source: https://baserow.io/user-docs/duration-field

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Duration field

The Duration field in Baserow is specifically designed to store time durations measured in hours, minutes, seconds, or milliseconds.

In this section, we will explore the duration field in Baserow, ideal for tracking time-related data like task durations, call lengths, event lengths, video lengths, etc.

## Overview

You can use this field to easily store information about the duration of projects, tasks, or meetings, and perform further manipulations with this data.

The duration field type supports negative values.

![Add a duration field in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/8f77d58d-a36d-4475-86bf-edcde4a2c90d/Duration.png)

## Add a duration field

To add a duration field,

  1. Click the plus sign `+` to the right of your existing fields.
  2. Select the duration type and name the field. You can add a unique field name in the customization menu.
  3. Select **Duration** field from the list.
  4. Click **Create**.

## Duration format

You can set your preferred duration format from the drop-down options in the [field configuration menu](/user-docs/field-customization).

![Baserow Formats for days](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/8497a4a9-879f-4fa3-9233-2bee6c7cce13/Untitled.png)

  * **h:mm** \- This format is suitable for representing hours and minutes, such as 1:23.
  * **h:mm:ss** \- You can use this format to display hours, minutes, and seconds, such as 1:23:40.
  * **h:mm:ss.s** \- If you need to include deciseconds, this format allows you to represent hours, minutes, seconds, and deciseconds, such as 1:23:40.0.
  * **h:mm:ss.ss** \- This format accommodates centiseconds, enabling you to display hours, minutes, seconds, and centiseconds, for example, 1:23:40.00.
  * **h:mm:ss.sss** \- If you require even more precision, this format includes milliseconds, allowing you to show hours, minutes, seconds, and milliseconds, like 1:23:40.000.

Formats for days:

  * **d h** \- This format is suitable for days and hours, such as 1d 2h.
  * **d h:mm** \- This format is suitable for days, hours, and minutes, such as 1d 2:34.
  * **d h:mm:ss** \- This format is suitable for days, hours, minutes, and seconds, such as 1d 2:34:56.
  * **d h m** \- This format is suitable for days, hours, and minutes, such as 1d 2h 3m.
  * **d h m s** \- This format is suitable for days, hours, minutes, and seconds, such as 1d 2h 3m 4s.

## Formula support for durations

Duration fields allow you to perform basic mathematical operations directly within the [formula editor](/user-docs/formula-field-overview). This enables you to manipulate time values for calculations and analysis.

  * Multiplication (`*`): Multiply the duration by a number. This is useful for scaling durations, for example, doubling a task duration.
  * Division (`/`): Divide the duration by a number or other durations. This can be used to calculate durations based on ratios or percentages.

> Use formats displaying date intervals in days in [formulas](/user-docs/formula-field-overview) such as `today() - field('date')`.

The `tonumber` function allows you to convert a duration field into its equivalent number of seconds. This is useful when calculations require a standard unit of time. You can combine formula operations with `tonumber` to perform complex calculations on durations.

