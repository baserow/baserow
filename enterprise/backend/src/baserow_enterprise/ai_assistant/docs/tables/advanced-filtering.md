# Baserow Documentation

Source: https://baserow.io/user-docs/advanced-filtering

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Advanced filtering by a field

Advanced filtering allows you to create and combine condition groups to precisely display the rows that match your specific criteria.

In this article, we will cover how to create condition groups within the [filtering](/user-docs/filters-in-baserow), row coloring, and conditional form fields.

![Baserow advanced filtering](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/38286f1c-3b26-47bc-a22b-8e6f53a84e9a/Advanced%20filtering.png)

## Understanding condition groups

A condition group is a combination of conditions connected using **“AND”** or **“OR”** logic, enabling you to build complex filters tailored to your exact needs.

**AND Logic** : When conditions are combined with “AND” logic, all conditions within the group must be met for a row to be displayed. This results in a stricter filter. For instance, you could create a rule to “Show tasks that are in progress AND have a high priority”. In this case, only tasks meeting both criteria will be displayed.

**OR Logic** : When conditions are combined with “OR” logic, a row will be displayed if any of the conditions within the group are met. This allows for a more permissive filter. For example, you could set a rule to “Show tasks where the release date is within this month OR have a high priority”. In this scenario, tasks meeting either of these criteria will be displayed.

## Create a condition group

To create a condition group,

  1. Open a [table](/user-docs/intro-to-tables) in Baserow and navigate to the filtering options.

  2. Add conditions to the filter. These conditions represent the criteria that rows must meet. For example, add conditions like “Priority is High” or “Release Date is within this month.”

  3. Create multiple condition groups with **“AND”** or **“OR”** logic. For example, set a rule to “Show tasks that are in progress, AND have a high priority, OR show tasks where the release date is within this month”.

     * **“AND”** logic: Rows must meet all conditions within the group.
     * **“OR”** logic: Rows must meet at least one condition within the group.
  4. After setting up the condition groups, apply the filter. Baserow will display only the rows that meet your specified criteria.

## Using advanced filtering

**[Filtering](/user-docs/filters-in-baserow)** : Advanced filtering can be used within the standard row filtering, which allows you to filter data based on the specified conditions.

**[Row coloring](/user-docs/row-coloring)** : Apply advanced filters to determine the color of rows based on the conditions you define. This helps visually distinguish between different subsets of data.

**[Conditional form fields](/user-docs/guide-to-creating-forms-in-baserow)** : This allows you to dynamically adjust form fields based on the conditions.

## Combined date filters

With combined filters, you can combine different filter types to create powerful filtering combinations.

To use multiple date filters in Baserow:

  1. Access the [filter panel](/user-docs/filters-in-baserow) in your table.
  2. Choose the [date field](/user-docs/date-and-time-fields) you want to filter by from the list of available fields.
  3. Select the initial filter type, for example, “is before,” “is after,” or “is on.”
  4. Next, choose a specific date reference like “today,” “tomorrow,” “yesterday,” or a custom date by clicking the calendar icon.
  5. Click **Add filter** to create a multistep filter. This allows you to combine another filter type and date reference, further refining your search.

Example: Filter records due “before tomorrow” and “after yesterday.” This would display rows with deadlines falling within today.

> Experiment with different filter types and date reference combinations to create the most suitable filter for your needs.

![Multistep date filters](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/808a449f-ddd0-47d7-a782-7f79760b7bca/Multistep%20date%20filters.png)

## Related content

  * [Row coloring](/user-docs/row-coloring)
  * [Field configuration options](/user-docs/field-customization)
  * [View configuration options](/user-docs/view-customization)
  * [Filter by a field in Baserow](/user-docs/filters-in-baserow)

