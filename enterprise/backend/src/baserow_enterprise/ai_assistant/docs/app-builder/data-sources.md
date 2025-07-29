# Baserow Documentation

Source: https://baserow.io/user-docs/data-sources

---


## Overview

With Baserow, you can add multiple data sources to your application, even on the same page.

You don’t have to connect a data source to your Baserow application, but it’s essential if you want more than a simple site with static content. This link lets you get and change data in real-time, making for interactive and fun user experiences.

When you tie a data source to your Baserow application, the data shows up on the page right away. Changes to the data show up instantly in your application, and you don’t have to republish anything.

## Add new data source

Let’s explore how to connect a data source.

Navigate to the top navigation bar on the left-hand side of the page, where you’ll find options for [Elements](/user-docs/elements-overview), Data, and [Page settings](/user-docs/application-builder-page-settings).

To add a new data source, click on Data Source in the top navigation bar. A popup will appear, displaying a list of all currently connected data sources, along with an option to add a new one.

  1. Click **Add new data source**.

  2. Select a service type.

     * Get single row - Finds a single row in a given table.
     * List multiple rows - Finds a page of rows in a given table.

![Add new data source in Baserow ](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/913b0e52-5768-4f8b-99b7-f5c4499d26ae/Untitled.png)

  3. Select an integration from the dropdown menu or click **Add new integration** directly. Learn more about integrations and how to configure them.

  4. As soon as you select a service type and integration, the element settings will become available.

  5. Select a [Database](/user-docs/intro-to-databases), [Table](/user-docs/intro-to-tables), and [View](/user-docs/overview-of-baserow-views) from the [workspace](/user-docs/intro-to-workspaces). The items in the list can be sorted and filtered according to the sorting and filtering configuration of that particular view.

  6. When you select the _Get single row_ service type, you need to enter or map a [row ID](/user-docs/overview-of-rows#what-is-a-row-identifier) to retrieve a single row in a given table by its ID. Leave this value empty to return the first row in the table.

> To dynamically input a [row ID](/user-docs/overview-of-rows#what-is-a-row-identifier) and retrieve a single row in a given table by its ID, add a [page parameter](/user-docs/application-builder-page-settings) to the page or add a [user source](/user-docs/user-sources).

![Retrieve a single row in a given table by its ID](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/00527587-cb5b-478f-8bd1-77b83e6822ad/Untitled%201.png)

## Filter data source

Data source filters allow you to display Baserow table rows based on specific conditions you define. Before diving in, you must select a table to start using data source filters.

Learn more about [filters in Baserow](/user-docs/filters-in-baserow).

To show rows that apply to the conditions set:

  1. Click **\+ Add additional filter**.
  2. Select any field from the dropdown menu to apply the filter.
  3. Specify the condition you wish to use for filtering.
  4. Define the value of the field to display, such as a specific word, status, or numerical value.

The items in the list will be filtered according to the filtering configuration of that particular view.

![Filter data source](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/a68f5dac-22f7-47b2-8740-f28b27e4c23d/Untitled%202.png)

You have the flexibility to filter rows by selecting multiple fields and applying various filters simultaneously using either `And` or `Or` conditions.

### Apply filters in the Application Builder

Understanding how filters interact between the Database and the Application Builder is important. It allows you to effectively manage filters between your database and the Application Builder, ensuring that your data is filtered precisely as needed.

**Selecting a table without a specific view:**

When selecting a table from the database without specifying a particular view in the data source filter configuration, any filters associated with views in the table won’t affect the results in the Application Builder. This means you can independently filter the rows displayed in the Application Builder, regardless of any view filters from the database.

This is useful when the views in the database table already have specific filters that you prefer not to use in the Application Builder.

**Selecting a table and view to apply an additional filter:**

When you select both a table and a view in the data source filter configuration, the filters you set are applied. Additionally, any filters present in the selected view within the database table will also be applied in the Application Builder. In this case, the filters at the table-level take priority, and then the filters at the Application Builder level only filter down the visible rows.

This is useful when you have specific filters in the view within the database table that are essential, but for further filtering in the Application Builder, additional filters are required.

### Use formula to filter data source

You can enter plain text or use formulas for certain filters of your data sources. It can be used in conjunction with [page parameters](/user-docs/application-builder-page-settings) to define what to fetch from a data source and works with a _Get row_ service type if you don’t specify the [row ID](/user-docs/overview-of-rows#what-is-a-row-identifier).

To add a formula to filter data, use the “Sum” symbol next to the field value:

![Formula to Filter data source in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/81208b12-5689-4ef5-99c3-d4f0f51cfcdb/Untitled%203.png)

## Sort data source

> This option is available for the _List multiple rows_ service type.

Sorting data sources in Baserow puts data in order based on specific criteria, like their names or numbers.

When you select a field to sort by, Baserow arranges the rows based on that field’s values. You can even choose multiple fields if you want to sort by more than one criteria, like first sorting by name and then by age.

Learn more about [sorting data in Baserow](/user-docs/guide-to-grid-view#sort-grid-view).

Click **Sorts** → **Add additional sort** to select a field to sort rows by. This will reveal any sort applied.

Each field will have ascending and descending order options.

![Sort data source](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/87132eda-aaa2-497d-aa17-4bc5c663ac9c/Untitled%204.png)

You can add more sorts by picking more fields to sort by. To apply a new sort, click the **Add additional sort** and then select another field from the dropdown menu.

### Apply sorts in the Application Builder

If you apply sorts, regardless of whether you select a view, only the sorts defined within the data source configuration will be applied to your data. This ensures that the sorting criteria you specify within the Application Builder take precedence over any predefined sorts associated with the selected view.

**When no sorts are applied:**

If you do not apply any sorting configurations within the data source configuration, and you have selected a view for your data source, the sorting criteria defined within the selected view will be used. In this scenario, the sorting rules set within the view settings will control the table rows displayed.

This allows you to tailor your sorting preferences according to your specific requirements, whether using the sorting options within the data source configuration or relying on the predefined sorts associated with the selected view in the database.

## Refresh data source

Refreshing a data source triggers an update of the data for the [selected element](/user-docs/elements-overview). It verifies if there have been any changes to the data in the source since it was last retrieved. This action is particularly useful after you’ve created or updated a row of data, ensuring you’re working with the most recent information.

Click **Refresh fields from data source** located within the General panel on the right side of the application interface to verify if any changes have been made to the underlying data source and incorporate those changes into your element.

![Data source refresh action for the Application Builder](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/fbb91832-6fbf-4842-a0ed-fce23566cfb5/Data%20source%20refresh%20action%20for%20the%20Application%20Builder.png)

## Search data source

To search the data source, specify a search term. You have the flexibility to choose the term for the search, giving you control over the query’s focus.

If no specific term is provided, the search will encompass all list items, offering a comprehensive view of the available data.

![Search data source](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/dd7aeeee-edad-47bd-9640-5d3f28f0d51f/Untitled%205.png)

## Share data source

Shared data sources in Baserow’s Application Builder allow you to add a data source that’s usable across multiple pages within your application. This boosts efficiency and saves time so you don’t need to add the same data source on multiple pages.

To create a shared data source, go to the ‘Data Sources’ tab. There, you can set up ‘Share between pages’ for a new data source or an existing one, marking it as available throughout different pages.

![Image: Shared data sources in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b71bc3ae-9917-41cd-a75d-8e434974d5d6/shared_data_sources.webp)

## Delete data source

Deleting a data source permanently removes its associated information from the application.

To remove a data source from an application:

  1. Identify the data source you wish to delete.
  2. Locate the trash icon positioned on the right-hand side of the data source.
  3. Click on the trash icon to initiate the deletion process.

