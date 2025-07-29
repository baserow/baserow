# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-date-time-picker-element

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Application Builder - Date-time picker element

The date-time picker element offers a user-friendly way to input dates and times in your application. Rather than typing dates manually as text strings, users can select dates from a calendar interface. You can configure the element to show or hide the time field and set the date and time format.

![Image: Baserow date_time_picker](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/132f134d-6ec5-477f-b703-b26b01060dbf/date_time_picker.webp)

## Overview

The date-time picker enables you to select specific dates and times for your records using this intuitive date-time picker. Ideal for scheduling events, tracking deadlines, recording timestamps, and more.

You can configure the element properties, and [customize its appearance](/user-docs/element-style) from the element settings.

## Add the date-time picker to an application

To add a date-time picker element, access the elements panel and select the date-time picker.

Once added, place the date-time picker element wherever you want it on the page. Don’t worry if it’s not perfectly positioned initially; you can always move it later.

[Learn more about how to add and remove an element from a page.](/user-docs/add-and-remove-elements)

Then, you can configure the date-time picker element’s properties to make it function and look the way you want. This involves settings related to the date-time picker element style.

## Configuring the date-time picker element

The date-time picker element can be configured with the following options

  * **Label:** Enter a descriptive label for the date-time picker field. This label will be displayed to users.
  * **Default value:** Optionally, set a default date-time value that will be pre-populated in the field.
  * **Required:** Check this box to make the field mandatory for users to fill.
  * **Date format:** Select the preferred date format from the dropdown list. Options include: 
    * **European (25/04/2024)** : Day/Month/Year format
    * **US (04/25/2024)** : Month/Day/Year format
    * **ISO (2024-04-25)** : Year-Month-Day format
  * **Include time:** Check this box if you want users to be able to select a specific time in addition to the date.

The Application Builder allows you to bind the label or default value to [data sources](/user-docs/data-sources). This allows the date to update dynamically based on user input or application logic.

By customizing these style properties, you can create inputs that match the look and feel of the page.

