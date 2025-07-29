# Baserow Documentation

Source: https://baserow.io/user-docs/guide-to-calendar-view

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Calendar view

In this section, we’ll cover getting started with Baserow calendar views. Visit this support section to [learn more about views in general](/user-docs/overview-of-baserow-views).

> The Calendar view is a feature available exclusively for Premium users. Users on the free plan cannot create or use the Calendar view. If your account doesn’t have access to the premium features, you cannot use the Calendar unless you [upgrade your plan](/pricing).

![Baserow Calendar view Overview](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/65a48f6f-6d66-4ef5-9a0a-90a3c87e739d/Calendar%20view.png)

## Overview

The Calendar view allows users to view, interact with, and visualize information according to dates. It is particularly useful for managing resources, planning, and scheduling. With the Calendar view, you can easily see how table rows correspond to specific dates, making it an effective way to keep track of events, deadlines, schedules, and other important information.

To use the calendar view, your table must contain a date field type:

  * [Date field](/user-docs/date-and-time-fields)
  * [Last modified field](/user-docs/date-and-time-fields#last-modified-field)
  * [Created on field](/user-docs/date-and-time-fields#created-on)

Baserow view options are available in the view bar. Click the ellipsis icon in the view bar and choose a view option:

  * [Import file](/user-docs/import-data-into-an-existing-table)
  * [Duplicate view](/user-docs/view-customization#duplicate-a-view)
  * [Webhooks](/user-docs/view-customization#create-webhooks)
  * [Rename view](/user-docs/view-customization#rename-a-view)
  * [Delete view](/user-docs/view-customization#delete-a-view)

![Calendar view options](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/aab550b7-c373-4c01-a082-1ad2ce126e36/Screenshot_2023-04-04_at_12.32.40.png)

You can search in the Calendar view and instantly see the filtered calendar cards. This is useful if you need to quickly sift through a lot of information in a calendar, cutting down the time it takes to find a specific event.

## Create a Calendar view

> A [date field](/user-docs/date-and-time-fields) must exist in your table to create a calendar view.

To add a Calendar view:

  1. Select the table to which you would like to add the Calendar view.
  2. Go to the [view switcher](/user-docs/create-custom-views-of-your-data#switching-between-views) by clicking on the existing view at the top of the table.
  3. click on the **Calendar +** button.
  4. Name the view and select a view type. The default view type is [collaborative](/user-docs/collaborative-views).
  5. Click **Add Calendar**.
  6. Choose the data you want to see in your calendar by selecting the date field you want to use for the view.

When you select a date field, your calendar view will populate with the rows from that date field.

![Create a Calendar view](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/f0bd0c21-43a6-4cef-b983-86c019aed633/Deadline_tracker.webp)

> To go back to the previous month or move forward to the next one, use the right and left arrows above the view. Click **Today** to quickly return to the current day.

## Create an event

You can quickly create an event for a specific time from the Calendar view. Creating an event will add a new row to the table.

To create an event,

  1. Open the Calendar view in your table.
  2. Click the `+` button that appears when you hover over any date on the calendar.
  3. Add the relevant event details to the fields.
  4. Click **Create**.

> Right-clicking on an event will provide a context menu with a **Delete** option. Deleting a row removes the data from the table. Always double-check the row content before deleting it to avoid accidental data loss.

## Calendar view options

### Edit an event you’ve created

  1. Open the Calendar view in your table.
  2. Click on the date card you want to edit to open it in a row edit modal.
  3. Make changes to the fields.
  4. Optional: Click “Show hidden fields” to see all the fields and edit them directly from a calendar.
  5. At the top of the page, click `X` to save and close the row edit modal.

### Select a color

Use the [row coloring](/user-docs/row-coloring) feature to give the date fields on the calendar a unique color.

When you create an event, you may specify what color it will appear in your calendars. You can add conditions by clicking on the **Add condition** button. Users will not be able to see the color you’ve assigned unless you’ve granted them access to your calendar. [Learn how to manage your permissions](/user-docs/managing-workspace-collaborators).

This allows you to customize the appearance of the cards based on your specific needs, providing effective and targeted information delivery.

![Select a color](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/812a0966-c836-4629-94c4-a10c6417652e/Screenshot%202023-05-23%20at%2012.21.07.png)

### Customize calendar labels

Customizations for field display are saved for each view, so you can have different preferences for your data without affecting all your views. Each modification to the view is saved, so you can easily refer back to it.

To show or hide a field in a calendar view,

  1. Open the Calendar view in your table.
  2. From the calendar view bar in the upper right corner of the view, click **Labels** in the view bar.
  3. By selecting this option, you will be presented with a menu of options for customising the appearance of the events in your calendar.
  4. Click the toggle next to the name of that field to turn on the fields you want to display and turn off the fields you want to hide.

> The **Labels** button toggles between two modes: hidden mode, where the toggle is greyed out and switched to the left, and showing mode, where the toggle is green and switched to the right.

You can toggle individual record fields or use the **Hide all** and **Show all** buttons to choose what fields you want your calendar to display.

![Customizing labels](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/6336f593-f28f-408d-84bb-183e68cc8812/date_field.webp)

You can also change the order of the fields on the cards by clicking and dragging the drag handles next to the field names.

### Change the associated date field

The **Displayed by [field]** option in the view bar lets you know which field is currently used for the calendar view.

To change the calendar view’s associated date field, click the calendar icon in the view bar to bring up the date picker. Then select a new date field from one of the table’s date fields to place dates on the calendar.

![Change the associated date field](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b10e2def-7f68-4fa7-84c0-508d1e6e27dd/change_date_field.webp)

### Display date by formula field

Use a date [formula field](/user-docs/formula-field-overview) to specify the dates to display. This allows you to specify the criteria for displaying the cards.

By using a date formula field, you can choose a date field you would like to use for a Calendar view while taking into account elements such as weekdays, weekends, specific dates, and even unique conditions.

![Display date by formula field](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9058239f-e714-430f-b1fa-fa4b01c78056/Screenshot%202023-05-23%20at%2012.16.14.png)

## Share view

A Calendar view can be shared with anyone once it has been created. When sharing the view, you can control how others see what you share by using Filters or Hide fields.

Share your calendar publicly:

  1. Open the Calendar view in your table.
  2. From the calendar view bar in the upper right corner of the view, click **Share view** in the view bar.
  3. Click **Create a private shareable link to the view**.

## Sync to an external calendar

You can synchronize your Calendar View with external calendar applications, ensuring your events and deadlines are always up-to-date across different platforms. This is handy for managing project timelines, scheduling events, or tracking important dates seamlessly.

To sync your calendar

  1. Navigate to Calendar View: Start by opening the Calendar View in your Baserow table.
  2. Share the Calendar View: Click on the **Share view** button located at the top of the Calendar View interface.
  3. Choose **Sync to an external calendar** from the options.
  4. A unique link will be generated. Copy this link to use in your external calendar application.
  5. Add to your external calendar: Open your external calendar application (e.g., Google Calendar, Outlook, Apple Calendar) and find the option to add a calendar by URL or subscribe to a calendar. Paste the copied link into the provided field.

Once completed, your Baserow Calendar events will automatically sync with your external calendar, reflecting any updates made in real-time.

![Sync to an external calendar](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2a939db4-05fe-4732-a1b0-abe4994d7193/Sync%20to%20an%20external%20calendar.jpg)

**Note:** By default, views now display a maximum of 20 linked items. If you need to access more than 20 linked items, use the search functionality within the row select modal to find the specific items you need, or adjust the view settings of the linked table to filter the results.

## Related content

  * [View configuration options](/user-docs/view-customization).
  * [Create a grid view](/user-docs/guide-to-grid-view).
  * [Create a gallery view](/user-docs/guide-to-gallery-view).
  * [Create a form view](/user-docs/guide-to-creating-forms-in-baserow).
  * [Create a kanban view](/user-docs/guide-to-kanban-view).

