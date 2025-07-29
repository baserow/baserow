# Baserow Documentation

Source: https://baserow.io/user-docs/date-and-time-fields

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Date and Time Fields

The date field type displays values as dates or times. Baserow date and time fields allow users to track and organize events, deadlines, and appointments in a clear and organized way. With date and time fields, users can easily create calendars, reminders, and schedules that can be shared with teams, clients, or stakeholders.

In this section, we will explore the different types of date and time fields available in Baserow, how to set them up, and how to use them effectively to streamline your workflow and keep everyone on the same page.

> Learn more about [multistep date filters](/user-docs/advanced-filtering)

## Adding date field

To add a date field,

  1. Click the plus sign + to the right of your existing fields.
  2. Select the date type and name the field. You can add a unique field name in the customisation menu and choose a date format by clicking the Date format dropdown menu.
  3. Click **Create**

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b7b02a43-1f5b-46e7-a5a4-eebb482a086f/Screenshot_2022-07-13_at_23.01.30.png)

You can manually enter a date (and time) into a cell, or you can use the calendar picker to quickly choose a recent date. The calendar and time picker makes it easy to choose a certain day and time when updating a date or time.

You can format the date field, and insert an automatically updated timestamp based on a [selected timezone](/user-docs/working-with-timezones).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/563364f6-26bd-4e9b-9794-c3bdb3bee188/Screenshot_2022-07-13_at_23.03.57.png)

## Format a date and time field

You can modify the format of the date when you customise the date and time formats. From the field options, you can change how the date field values are formatted, choose your preferred date format, and decide whether or not to include a time.

Edit your field by clicking the dropdown beside the field you want to change and click **Edit field** , then the **Save** button.

### Setting a date format

Any datetime field has the potential to be set to a date format. You can set your preferred date format from the drop-down options in the [field configuration menu](/user-docs/field-customization).

  * European `DDMMYYYY` (20/02/2020)
  * US `MMDDYYYY` (02/20/2020)
  * ISO `YYYYMMDD` (2020-02-20)

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/6916ec04-12d9-4278-af55-3eda711efc28/Screenshot%202022-12-05%20at%2017.51.33.png)

### Setting a time format

Any date field can include a timestamp. You can include time for a datetime field by selecting the “Include time” option from the [field configuration menu](/user-docs/field-customization).

You’ll be able to select your preferred time format from the drop-down options.

  * 24-hour format (23:00)
  * 12-hour format (11:00 PM)

By selecting the “Include time” option, you can manually select a time from the drop-down menu or enter a specific time.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/3141e3fd-e109-47aa-a6d8-44191ed8d0b7/Screenshot%202023-03-08%20at%2014.35.13.png)

## Created on

When creating a new field type, you can set it to display the date and time when a row was created. The date (and, optionally, the time) that a row was created will be automatically displayed in the **Created on** field type.

Note that there is no way to directly modify the data in the cells in the **Created on** field because the date each row was created will always be the same.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/5a594fcd-fcc3-4eb6-b81b-056d39681ba1/Screenshot_2022-07-13_at_22.59.41.png)

## Last modified field

The last modified field will always be the most recent date and time that a row was edited by a user. The computed field automatically returns the date and time of the last modification.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/747f0d89-5d87-4948-a067-bafbacd176fc/Screenshot_2022-07-14_at_08.20.59.png)

Learn more about the [last modified field](/user-docs/last-modified-field).

