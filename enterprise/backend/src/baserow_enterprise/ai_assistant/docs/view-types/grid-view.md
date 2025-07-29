# Baserow Documentation

Source: https://baserow.io/user-docs/guide-to-grid-view

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Grid View

In this article, we’ll cover the process of creating and managing a grid view. Visit this support section to [learn more about views in general](/user-docs/overview-of-baserow-views).

## Overview

If you’re used to using a traditional spreadsheet program like Microsoft Excel or Google Sheets, then you’ll feel right at home with the Baserow grid view. The grid view is the starting point to manage your data. Within this view, you can sort, filter, view, edit, and export data at record speeds.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-20_at_13.56.17.png)

A grid view offers a more condensed way to look at a large number of items. A user can have a lot of data on a table, but still, be able to view all – even when the data is complex.

You can export grid views and non-members can access data contained via a public link.

You may customize a grid view by clicking the ellipsis next to it and making changes. To choose an action, click the ellipsis `•••` at the top of any column:

  * Export view
  * Webhooks
  * Rename view
  * Delete view

## Create a Grid view

To add a grid view:

  1. Open up the view dropdown by clicking on the view switcher in the top left-hand portion of the table
  2. Click on the **Grid +** button to bring up a menu where you will enter a name for this new view
  3. Click **Add grid**.

The grid will be populated with existing data from other views.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/abf69f3512da8375640e8a31c84f7733dc9f1e5c.webp)

Using the view switcher at the top-left of the table, you can easily switch between views you’ve created.

> Tip 💡: Using your keyboard shortcut, `Shift` \+ `Enter` to move to the row below.

To delete a grid view, click the view menu button (…) and then select ‘**Delete view** ’ at the bottom of the dropdown menu that appears.

### Selecting Multiple Rows

You can select multiple rows in the grid view to perform bulk actions. There are two ways to select multiple rows:

**Using Checkboxes:** Hover over the row number on the left side of the grid. A checkbox will appear. Click the checkbox to select the row. You can select multiple rows by clicking the checkboxes for each row.

**Using Keyboard Shortcuts:**
    
    
    *   Select the first row you want to include in your selection.
    
    *   Hold down the `Shift` key and click on the last row you want to include. This will select all rows between the first and last selected rows, inclusive.
    

Once you have selected multiple rows, you can perform actions such as deleting, duplicating, or exporting the selected rows. The available actions will appear in a toolbar at the top of the grid.

## Filter grid view

Grid views can be filtered. You can [use filters](/user-docs/view-customization) to quickly locate those tasks that match multiple criteria. Simply select two or more filters from the list of filters. For example, you can limit which linked rows users can choose when filling out your form by using filtered views. The form’s users can only choose from the related records that are present in the selected view by choosing a view from this dropdown.

To add custom filters, you can show rows that apply to your conditions by clicking on the **\+ Add filter** button.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-29_at_02.44.54.png)

> Tip 💡: Double-click a grid field name to make quick edits.

## Sort grid view

Sorting information is an integral part of the creative process for many people. Baserow makes that process simple by letting you sort rows by appropriate fields. You can sort the view automatically or manually to change the order in which the rows appear.

If you share a view with non-members using a [view share link](/user-docs/public-sharing), note that sorting conditions applied to the view will be retained even after the view is shared.

### Default sorting

When you create a new table, your data is sorted by when a new row is added. You can sort your rows in a view such that they display in a specific order based on the values in selected fields.

### Automatic sorting

Click the **sort** button in the view bar to apply a sort to your current view. The sort menu will appear to reveal any sorts applied.

You can sort your rows by clicking the **Choose a field to sort by** option. Once you’ve selected the field you want to sort by from the dropdown, fields will automatically be ordered based on the sort option.

You can add more sorts by picking more fields to sort by. To apply a new sort, click the **Choose a field to sort by** and then select a field from the dropdown menu.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/60f6bbc2bc709f3aa9b93c1c262fe18230733813.webp)

If you use the sort conditions, you will not be able to manually reorder rows with the drag-and-drop functionality.

When there are a few different columns to be sorted by, add the options in the order you want the fields to be sorted by.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-07_at_10.44.47.png)

To remove a sorting option, click on the `X` button to the left of the sort option.

### Manual sorting

Thanks to the flexibility of Baserow views, you can rearrange your data to best fit your view of things in ascending or descending order. Sorting your table manually will allow you to organize your work in whatever way suits you.

You can change the order of rows when they are sorted by default by clicking and dragging the row using the drag handle on the left side of the row to manually reorder rows.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/52b3d6d6bf91456aae9aabd55832450cd1b5cb12.webp)

## Share grid view

After creating a Grid, you have the option to [share the link with anyone](/user-docs/public-sharing). When you decide to share the view, you have the flexibility to control how others perceive the shared information by utilizing Filters or Hide fields.

To embed a view via an iframe. Share a grid view publicly, copy the publicly shared URL, and replace `YOUR_URL` in the code snippet below:
    
    
    <iframe src="YOUR_URL" frameborder="0" width="100%" height="400"></iframe>
    

## Hide fields

The hide fields options within the grid view allow you to choose what you want to view and what you don’t. You can hide or show the fields in a table so that some of the fields are not visible, except for the primary field, which cannot be hidden. This is useful if you share a view via a public link and want to restrict access to some data.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-21_at_15.41.22.png)

> Note that you won’t be able to hide/show the [primary field](/user-docs/primary-field).

To show or hide a field,

  1. select the ‘**Hide fields’** link at the top of the page.
  2. Click the toggle next to the name of that field to turn on the fields you want to display and turn off the fields you want to hide.

Record fields can be toggled individually or, you can quickly hide/show all fields using the **Hide all** or **Show all** buttons.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/96bc22ef5ee8c567bedac0b1864f4cdd294663d5.webp)

The Hide Fields dialog enables you to hide (gray out) or display (green) individual elements in a layout. Baserow will show you a preview of the number of fields that are currently hidden. If fields in the current view are hidden, the hide fields button will be highlighted and show the number of fields hidden.

If you have a lot of fields, you can use the **Search fields** box to enter a term to help you find the field to hide or show quickly. You can also reorganize the order of the fields.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/157605cc9a14c7ae0cc3a36a62bd5126c9f6aa06.webp)

Another way to hide or show individual fields from a grid view is by opening up an [expanded view](/user-docs/navigating-row-configurations) or by clicking on the field header, and then selecting the **Hide field** option from the dropdown menu.

## Adjust the width of a field

> The configurable row height feature allows you to adjust the height of rows in the Grid View. Learn more about how to [improve readability with row height options](/user-docs/navigating-row-configurations#configure-row-height).

By default, grid views display rows at a fixed width. Nevertheless, if you prefer to view more data within each cell, you have the option to adjust the column width. This attribute allows you to customize the width of columns based on the content present in the cells of that particular column.

To expand a single field at a time,

  1. Click and hold your mouse on the dividing line next to the title of any field to lengthen or shorten the width as desired.
  2. Drag the line to increase the width. You’ll see a blue bar appear with the indicator.
  3. Unclick at the desired width to view more information in each cell.

![Adjust the width of each field in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/28a7e27d781acc3f58d382bc7dd915fb420edaa1.webp)

## Footer aggregations

The footer aggregations compute values based on a field. Aggregations are performed to calculate values based on a specific field in a table.

By default, the footer summary for each field is empty. To obtain a summary of a specific field, [visit this support documentation](/user-docs/footer-aggregation).

**Note:** By default, views now display a maximum of 20 linked items. If you need to access more than 20 linked items, use the search functionality within the row select modal to find the specific items you need, or adjust the view settings of the linked table to filter the results.

## Related content

  * [View configuration options](/user-docs/view-customization).
  * [Work with gallery views](/user-docs/guide-to-gallery-view).
  * [Work with form views](/user-docs/guide-to-creating-forms-in-baserow).
  * [Work with kanban views](/user-docs/guide-to-kanban-view).
  * [Work with calendar views](/user-docs/guide-to-calendar-view).

