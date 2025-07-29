# Baserow Documentation

Source: https://baserow.io/user-docs/guide-to-kanban-view

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Kanban view

In this article, we’ll cover the process of creating and managing a Kanban view. Visit this support section to [learn more about views in general](/user-docs/overview-of-baserow-views).

> This view is restricted to the premium version only. Users on the free plan cannot create a Kanban view. If your account is not on our premium plan, you will not have access to the Kanban view unless your plan is upgraded.

## Overview

Are you the kind of person who organizes tasks in columns? Do you regularly use Trello and Asana or attempt an agile project only to find it too difficult to manage all your tasks in a single place?

As a powerful visual workflow, board view is a great choice for all agile teams to readily organize their data into a matrix of cards. But it offers a lot of advantages, even to teams that aren’t using the agile methodology.

You may customize a Kanban view by clicking the ellipsis next to it and making changes. To choose an action, click the ellipsis `•••` at the top of any column:

  * [Webhooks](/user-docs/view-customization#create-webhooks)
  * [Rename view](/user-docs/view-customization#rename-a-view)
  * [Delete view](/user-docs/view-customization#delete-a-view)

## Create a Kanban view

With the Kanban View, you can view your tasks in a new way by arranging them as cards on a board. This view allows you to visualize data at a glance and prioritize moving those tasks through the workflow.

To add a Kanban view:

  1. Select the view switcher (current view option at the top of the table) to reveal the view pop-up.
  2. Select **Kanban +** button and enter a name for this view
  3. Click **Add Kanban**.
  4. Select a single select field the cards should be stacked by or click **\+ add single select field** to create a new single select field.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/ffff8e973fc8938d864854f21df2c1cd23813dba.webp)

You can set up the Kanban view to provide you with a quick snapshot of the high priorities so you can focus on the most pressing items.

> Using the view switcher at the top-left of the table, you can easily switch between views you’ve created.

To delete a Kanban view, click the view menu button (…) and then select the **Delete view** button at the bottom of the dropdown menu that appears.

## Filter kanban view

Similar to the grid view, kanban views can be [filtered](/user-docs/view-customization). Filters allow you to show rows that apply to your conditions. You can streamline the data you get back to include only the data points that fit your needs, rather than having to read through everything.

## Customize cards

Customize the information displayed on the boxes using the ‘Customize cards’ options. You can organise the information you want to display in a variety of ways after you’ve added your Kanban view.

If you have a lot of fields, you can use the search box to help you find the field more quickly.

> Right-clicking on a card will provide a context menu with a **Delete** option. Deleting a row removes the data from the table. Always double-check the row content before deleting it to avoid accidental data loss.

### Cover field

The cover field is a defined [File field](/user-docs/file-field) that shows up on the top of the Kanban preview when you create it.

Your table must contain at least one file field, ideally an image, if you want to set your Kanban view’s cover field. If a file field is present, it can be selected as the view cover image when creating a Kanban view.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-29_at_09.45.17.png)

### Share view

Once you’ve created a Kanban view, you can share the link with anyone. When sharing the view, you can control how others see what you share by using Filters or Hide fields.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/0e6ab20c-9156-4da0-adf0-bf24573d4f77/Screenshot%202022-10-14%20at%2013.32.08.png)

### Hide/show field

Hide or show hidden fields in a Kanban view by clicking the **Customize cards** button in the view bar.

To show or hide a field,

  1. In the upper right corner of the view, click **Customize cards**.
  2. Click the toggle next to the name of that field to turn on the fields you want to display and turn off the fields you want to hide.

You can toggle individual record fields or use the **Hide all** and **Show all** buttons.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/5efd32bf0beee1572609c827fcf05e0b5f0eb944.webp)

The ‘**Customize fields’** button toggles between two modes: hidden mode, where the toggle is greyed out and switched to the left, and showing mode, where the toggle is green and switched to the right.

You can also change the order of the fields on the cards by clicking and dragging the drag handles next to the field names.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-15_at_08.07.43.png)

By clicking on a card to open up an [expanded view](/user-docs/navigating-row-configurations), you may either show or hide fields from the cards in your Kanban view.

## Group and reorder cards

Choose how your tasks are organised in your view by grouping them with a [single select field](/user-docs/single-select-field). All the cards in a kanban view’s stacks are existing rows in a table arranged according to the single select field selected to customise the way your tasks are shown in your view. The options in the single select field determine the stacks when the Kanban view is created. You can see what single select field the view is stacked by in the view bar.

### Move cards within a stack

You can move your cards within stacks by dragging and dropping them in the category you want them to be in. With the powerful drag-and-drop interface, you can reorganise the single select field by which the cards should be stacked. The single select field’s value will adjust to reflect the new stack if a card is moved from one stack to another stack.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b65ec8644393629b8edabb042ec57937edf61317.webp)

A card will show up in the **uncategorized** stack if the single select field that was used to stack the Kanban view contains no value. If a card with a single select field’s value is moved into the uncategorized stack, the field value is cleared.

### Change associated single select field

The ‘Stacked by [field]’ option in the view bar lets you know which field is currently being used for this Kanban view.

To change the single select field, click on the button and select a new field from the dropdown menu or create a new single select field with options.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-30_at_12.22.54.png)

## Card options

You can build stacks in the Kanban view using a single select field from your table.

### Create cards

Creating a new card will create a new row in the grid. To create a card,

  1. Select the ellipsis `•••` beside the view you want to edit.
  2. Select **Create card** to add the relevant details to the fields.
  3. Click the **Create** button.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-14_at_20.56.17.png)

### Edit stack

To edit a stack,

  1. Select the ellipsis `•••` beside the view you want to edit.
  2. Select **Edit stack** to change the colour scheme and stack name of the single select option.
  3. Click the **Change** button.

### Delete stack

Deleting the stack results in deleting the select option of the single select field, which might result in data loss because row values are going to be set to empty.

To delete a card,

  1. Select the ellipsis `•••` beside the view you want to edit.
  2. Select **Delete stack** to delete the single select field.
  3. Click the **Delete** button.

**Note:** By default, views now display a maximum of 20 linked items. If you need to access more than 20 linked items, use the search functionality within the row select modal to find the specific items you need, or adjust the view settings of the linked table to filter the results.

## Related content

  * [View configuration options](/user-docs/view-customization).
  * [Work with gallery views](/user-docs/guide-to-gallery-view).
  * [Work with grid views](/user-docs/guide-to-grid-view).
  * [Work with form views](/user-docs/guide-to-creating-forms-in-baserow).
  * [Work with calendar views](/user-docs/guide-to-calendar-view).

