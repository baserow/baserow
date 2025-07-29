# Baserow Documentation

Source: https://baserow.io/user-docs/guide-to-gallery-view

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Gallery view

In this article, we’ll cover the process of creating and managing a gallery view. Visit this support section to [learn more about views in general](/user-docs/overview-of-baserow-views).

## Overview

Baserow gallery view displays your data in list-like cards that support fields with multiple lines of text and files. Your rows are displayed in the gallery view as cards that highlight documents and images. The contents of the cover field are shown at the top of each gallery card.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-14_at_19.04.00.png)

You may customise a gallery view by clicking the ellipsis next to it and making changes. To choose an action, click the ellipsis `•••` at the top of any column:

  * Webhooks
  * Rename view
  * Delete view

> Using the view switcher at the top-left of the table, you can easily switch between views you’ve created.

## Create a Gallery view

To add a gallery view:

  1. Open the table that you want to add a gallery view to.
  2. Click the existing view at the top of the table.
  3. Select ‘**Gallery +’** from the view menu options among the new view creation list
  4. Name the view.
  5. Click ‘**Add Gallery’**

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-29_at_08.54.24.png)

To delete a gallery view, click the view menu button (…) and then select **‘Delete view** ’ at the bottom of the dropdown menu that appears

## Filter and Sort cards

Similar to the grid view, gallery cards can be [sorted and filtered](/user-docs/view-customization). Within the view, you can filter and sort data in multiple ways. Sorting your rows in one view only affects the view you’re now using to view your table; it has no bearing on the order of your rows in other views.

Data filtering allows you to see only the data you want to search on. This flexibility helps you categorize information as you need it. It provides easy access to your most important pieces of information.

Sorts allow you to sort rows by a field. You can use the sort option in the view bar to change how task cards are arranged on your gallery, or click and drag on cards to move them around.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/00cae85389fd45b4acb1ad51b826fc311ffe51cc.webp)

If the sort conditions are set, you will not be able to manually reorder the cards in the gallery by clicking and dragging them.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-30_at_16.47.59.png)

## Share view

In addition to Grid view, you can now [publicly share a Gallery view link](/user-docs/public-sharing) with anyone. When sharing the view, you can control how others see what you share by using Filters or Hide fields.

### Embed a view via the iframe tag

To embed a view via an iframe. Share a grid view publicly, copy the publicly shared URL and replace “`YOUR_URL`” in the code snippet below:
    
    
    <iframe src="YOUR_URL" frameborder="0" width="100%" height="400"></iframe>
    

You can create multiple views with different filters and easily share your data by creating a public link.

## Customize cards

You can customize which fields appear on the cards in your gallery view. Click the ‘**Customize cards** ’ button in the view bar to edit the cover field or hide/show fields from the gallery preview.

You can also use the search bar to quickly look for fields.

### Cover field

The cover field is a defined [File field](/user-docs/file-field) that shows up on the top of the gallery preview when you create it.

Your table must contain at least one file field, ideally an image, if you want to set your gallery view’s cover field. If a file field is present, it can be selected as the gallery cover image when creating a gallery view.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-14_at_20.51.10.png)

To change the cover field if you have more than one file field, choose a new cover from the cover field dropdown menu. You can decide not to have a cover field as well.

The cover image of a gallery view will be accessible when the [view is shared publicly](/user-docs/public-sharing).

### Hide or show fields

You may easily toggle fields to customize what data is shown on the Gallery preview. By using the toggle next to the relevant fields, specify the fields you want to show or hide.

  1. At the top of the view, click ‘**Customise cards’**.
  2. Toggle which fields should be visible or hidden next to the name of the field you want to hide or show, or by clicking the hide all and show all buttons in the arrange fields menu

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-14_at_20.43.36.png)

You can see which fields are visible (where the toggle is green and turned to the right) and which fields are hidden on the gallery cards (where the toggle is greyed out and switched to the left).

You can rapidly hide/show all fields using the ‘**Hide all** ’ and ‘**Show all** ’ buttons.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/068b6da1753bc07b4406e20d940fef74f0037464.webp)

You can hide or show individual fields from the cards in your gallery view by [expanding on a card](/user-docs/navigating-row-configurations#enlarging-rows) to see it in record detail.

### Reorder fields

By clicking and dragging the drag handles next to the field names, you can reorder the fields on the cards. Drag the fields to the desired location in the order pane to rearrange the fields.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9255efa902889b27c6c414bb365f5e3270c1be7a.webp)

**Note:** By default, views now display a maximum of 20 linked items. If you need to access more than 20 linked items, use the search functionality within the row select modal to find the specific items you need, or adjust the view settings of the linked table to filter the results.

## Related content

  * [View configuration options](/user-docs/view-customization).
  * [Work with grid views](/user-docs/guide-to-grid-view).
  * [Work with form views](/user-docs/guide-to-creating-forms-in-baserow).
  * [Work with kanban views](/user-docs/guide-to-kanban-view).
  * [Work with calendar views](/user-docs/guide-to-calendar-view).

