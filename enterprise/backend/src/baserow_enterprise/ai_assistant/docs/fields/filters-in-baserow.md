# Baserow Documentation

Source: https://baserow.io/user-docs/filters-in-baserow

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Filter by a field in Baserow

Filters in Baserow allow you to sort and refine your data to find the information you need quickly.

This article will walk you through how to use filters effectively in Baserow, providing you with a clear understanding of this feature’s functionality.

## Overview

Filters allow you to narrow down and sort your data based on specific criteria. They are used to display only the rows that meet the conditions you specify, making it easier to work with large datasets.

Filters help you quickly find the information you need, reducing clutter and enhancing your data management, whether you want to see entries from a particular date, items that match certain criteria, or need to sort your data in a specific order.

In the [Enterprise plan](/user-docs/enterprise-license-overview), users with the [editor role and lower](/user-docs/set-permission-level) in the collaborative views have filtering and sorting capabilities. These configurations will only be visible to these users and won’t be saved as a general setting for all collaborators.

Learn more about [advanced filtering in Baserow](/user-docs/advanced-filtering) to create a filter with multiple conditions.

## Add a new filter

You must choose a field, a condition, and a value before you can set a specific condition.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot%25202022-06-30%2520at%252013.57.13.png)

You can use a condition to create a rule that the records must follow to be visible in the current view.

To add custom filters to a view, you can show rows that apply to your conditions by clicking on the **Filter** link in the view bar at the top right of your table:

  1. Click **\+ Add Filter**.
  2. Choose any field you want to filter your table by from the dropdown.
  3. Choose the condition you want to use, i.e. Contains, Contains not, is, is not, is empty, is not empty, higher than, lower than, length is lower than, is date, is not date, is today, is days ago, in this month, is after date, is before date, day of month is, in this year, in this month, has, has not, etc.
  4. Define the value of the field you want to see, i.e. a specific word, status, or number.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/ae74a6d071629036c1c0c5664058bc7efb6d774c.webp)

You can easily remove filters by clicking the **`X`** icon next to them in the **filter** menu.

## Customize filters with multiple conditions

View only the rows that fit certain criteria, depending on what you need by customizing your filtering conditions with multiple conditions. To create more complicated filtering, we can chain together several conditions. For multiple filter rules, there are two types of logic: AND and OR. You can use this method to apply numerous filters at once using the `And` or `Or` conditions.

### AND conditions

Use `And` when you want **all** conditions to be met. Use AND logic to find items that fulfill all requirements within a collection of filter rules. For example, if you want to identify projects containing the status ‘In progress’ AND ‘Urgent’ in a table, click `And` before adding the second rule.

### OR conditions

Use `Or` when you want **any** condition to be met. Use OR logic to find items that satisfy at least one of a set of filter rules. For example, if you want to identify projects containing the words 'Rebranding website OR ‘User portal’ in a table, click `Or` before adding the second rule.

To add another condition for a color, click the ‘**Add condition** ’ button. Adding a second condition creates a condition workspace with all the conditions connected via `And` or `Or`.

## Disable and enable multiple filter options

You can toggle the ‘all disabled’ box to enable or disable all existing fields within the page. This will not remove the filters from the table but will only disable them from applying.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/035c1ac36f181c7337d47e0da10c1e2dcccab748.webp)

As you activate each filter condition, notice how the aggregated values at the bottom of the screen adjust accordingly to reflect the number of rows visible.

## Related content

  * [Advanced filtering in Baserow](/user-docs/advanced-filtering)
  * [Group by a field](/user-docs/group-rows-in-baserow).
  * [Work with grid views](/user-docs/guide-to-grid-view).
  * [Field configuration options](/user-docs/field-customization).

