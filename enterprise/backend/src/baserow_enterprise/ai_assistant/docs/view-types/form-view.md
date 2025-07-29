# Baserow Documentation

Source: https://baserow.io/user-docs/guide-to-creating-forms-in-baserow

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Form view

In this article, we’ll cover the process of creating and managing a form view. Visit this support section to [learn more about views in general](/user-docs/overview-of-baserow-views).

[Learn more about form modes in Baserow](/user-docs/form-survey-mode).

## Overview

Baserow Form view provides an easy solution for collecting information. Baserow forms are automatically built from your current table and provide you with the flexibility to customize fields, without creating a form from scratch.

> Formula, created on, count, UUID, rollup, last modified, and lookup fields are incompatible with form view.

When your recipients submit your forms, you can add fields and rules to automatically produce new rows. You can create a form view on any table on Baserow.

You may customize a form view by clicking the ellipsis next to it and making changes. To choose an action, click the ellipsis `•••` at the top of any column:

  * Webhooks
  * Rename view
  * Delete view

## Create a form view

To add a new form view to an existing table:

  1. Click the existing view at the top of the table.
  2. Select **Form +** from the popup
  3. Name the view.
  4. Click **Add form** to quickly create a form.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/5fe81ff9b5f9d3107f59248bfa9c74adcf5ea2bf.webp)

All of your fields are automatically populated based on each field listed in your grid view.

> Using the view switcher at the top-left of the table, you can easily switch between views you’ve created.

To delete a form view, click the view menu button (…) and then select ‘**Delete view** ’ at the bottom of the dropdown menu that appears.

## Customize form display

After you’ve added your form view, you can organise the information you want to display in a variety of ways. You can alter how a field appears to the end user and also choose which fields will appear on your form and in what order.

To change the Submit button text, click on the pencil icon next to the ‘**Submit** ’ button and add the text of your choice.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-29_at_00.40.30.png)

### How to add fields

Adding a new field to your form is simple. All you have to do is select the required fields on the left sidebar to begin collecting information.

To add a new field, you can either select individual fields or click the ‘**add all** ’ button.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-08_at_20.11.18.png)

You can add a newly created field that doesn’t currently exist in your table by clicking the ‘**\+ Create new field** ’ button that appears in the Fields sidebar.

### How to remove fields

To remove a field from the form, select the field to display the options then click on the ‘eye’ icon.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/6b3fc3079c69e8249910e96df09e0281124d1809.webp)

### Control field options

Click on the header section to add a title and description to your form.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-29_at_03.17.24.png)

For all the fields, you can also change the name as it will appear on the form and subtitle to something more descriptive of what the field is for and the information that it holds.

You can also make this field required by using the **Required?** toggle.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-29_at_02.58.22.png)

You can link to multiple [link to table](/user-docs/link-to-table-field) entries in the form view. You can choose between “Single” and “Multiple” options for displaying the field. The “Multiple” option includes a `+` button that allows you to add another dropdown to select a value from.

![linking to multiple link to table entries in the form view](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/91f6e6ad-5cce-4153-9be8-3577f1f53476/Form.png)

### Add custom branding with a cover image and logo

After customizing your form’s fields, you can further customize the look of your form. To add a logo, click on the ‘**Add a logo’** option and upload the desired image.

To upload a cover image, click the grey area at the top of the form where it says ‘**Add a cover image** ’ and then upload the chosen image.

The same can be followed when you want to remove the image or replace it with a new one. Select the fields and the appropriate images.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/c95b49cd2a0d68714468cfae1670218215ada6ae.webp)

### How to reorder fields

Once you’ve added your questions, you can reorder them.

When working with the Form mode, you can reorder the questions on your form by clicking on a field and dragging it using its drag handle.

To reorganize the form layout, select the field you want to remove and then use the `⠿` to move the order of the fields.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/e8d9422b0c45101399369e2c86c8b6303a0038a7.webp)

Reorder the fields in the Survey mode by clicking the ‘Order fields’ link at the bottom of the screen. This will bring up a popup of all the fields in the form. Select the field you want to remove and then use the handle ⠿ to reorder the fields.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9176b5b4-fb11-4d46-a22a-7e279b6be296/fd2fc9d863fc0204cf5c8121256ad168f40cac9d.webp)

### Radio and checkbox components

You can choose a radio button for single selection fields and a checkbox for multiple selection fields in the form view. These options make forms look better and simpler for people to select their choices while completing them.

![Components for Baserow form view](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/587eb53d-7665-4e3c-adb7-df81ec0923dc/New%20form%20components.png)

### Customise select options

This gives you control over which options are displayed in [single](/user-docs/single-select-field) and [multiple select fields](/user-docs/multiple-select-field). You can customize the available choices to show only specific options, giving you better control over form organization.

To configure select options in Form View:

  1. Open a Form View
  2. Find the [single](/user-docs/single-select-field) or [multiple select field](/user-docs/multiple-select-field) you want to customize
  3. Choose which options should be available in the form

![Image: Baserow form_view_select_options](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/6f7b4063-5ddb-4f00-9a08-72a81a2073a8/form_view_select_options.webp)

## Form conditions

Form conditions allow you to control what happens when specific data is entered in a particular field. Conditional logic can be used to hide and show form fields only if any of the criteria are met. It will show fields in a form based on the provided values for previous fields. Creating conditions for forms works the same as [Baserow filters](/user-docs/view-customization#filter-view).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/45d51db0-c72a-4ff6-9874-54cbd114f6b6/form%20conditions.png)

## Configure form post submission

You may customize what happens once a form is submitted.

### Show a message

After a form has been submitted, you can customize the message that will be shown on the “Thank You” page by typing it in the ‘**Show a message** ’ box. After users click a form’s ‘**Submit button** ’, they will see a message you have customized.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-29_at_02.27.59.png)

Use `{row_id}` to include the newly created row id in the URL.

### Redirect to URL

To redirect a respondent to a specified URL after submission, enter the URL to the web page you want to redirect to in the URL field. The web browser will be redirected to the URL you specify, rather than defaulting to the default Thank You page.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-29_at_02.21.05.png)

> You can opt into [receiving notifications when someone fills out the form](/user-docs/notifications#notifications-for-new-form-submissions). To turn on these notifications, just switch on the “receive form notifications” button found at the bottom of the form edit page. This helps you stay updated about new form entries and allows for fast responses when required.

## Share form

Anyone, including Members, can share a form. To share the link with anyone when you’re done creating your form, click on ‘**Share form** ’ at the top of the screen and proceed to create a private shareable link to the form.

[Learn more about public sharing in Baserow](/user-docs/public-sharing).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-09_at_13.04.45.png)

## Pre-filling a form

Whether you are capturing leads, collecting survey results, or registering people for an event, you can get responses directly into your table by using the form view in Baserow. Forms can be prefilled to help the user fill in the form faster. With the pre-filling feature, you can use pre-fill parameters in the URL of the form to pre-fill specific fields making forms even more powerful.

If you want to prefill a form with data you can do so via query parameters added to the public form URL. These query parameters are prefixed with `prefill` to avoid any collision with potential future query parameters.

> You can pre-fill both the field name and displayed name in forms.

To pre-fill a form,

  * Copy your form URL.
  * Add URL parameters in the format: `?prefill_<field_name>=<value>`
  * Share the pre-filled link.

> The `<field_name>` and `<value>` values are placeholders. You will need to match the field names and values to the corresponding data in your specific table.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d56d70c8-f001-40bc-8006-f99140aee498/prefill%20values%20dynamically.png)

> All fields which are available in the form can be prefilled. Note that the values are case-sensitive.

**Spaces**

Spaces in the field name are replaced with `+` to avoid any issues with the query parameter.
    
    
      ?prefill_my+field=Mike
    

**Multiple fields**

If you want to prefill more than one field, you can do so by adding the `&` ampersand symbol between the fields. To avoid naming conflicts, prefix each field name with `prefill` to prefill your field.
    
    
      ?prefill_Focus=Infrastructure&prefill_Name=Thor
    

**Special field types**

Generally, the prefill value is the same as the field’s value. However, there are some exceptions where the value is translated to a different value.

**Single Select**

A single select field type can accept the value that is shown in the select dropdown.
    
    
      ?prefill_single+select=Mike
    

**Multiple select field type**

A Multiple Select field can accept the value that is shown in the select dropdown and can also accept multiple values. If you want to prefill more than one value in a multiple-select field, you can do so by adding a `,` between the values.
    
    
      ?prefill_multi+select=Mike,John
    

**Rating field**

A rating field accepts a number to indicate how many stars should be filled.
    
    
      ?prefill_rating=3
    

**Link row field**

A link row field can accept the value that is shown in the select dropdown.
    
    
      ?prefill_link+row=Mike
    

**Date field**

A date field can accept a date in the following formats and will use the date format of the field to parse the date.
    
    
    // Standards
    ISO_8601
    
    // General formats
    'YYYY-MM-DD',
    'YYYY-MM-DD hh:mm A',
    'YYYY-MM-DD HH:mm',
    
    // EU
    'DD/MM/YYYY', 
    'DD/MM/YYYY hh:mm A', 
    'DD/MM/YYYY HH:mm'
    
    // US
    'MM/DD/YYYY', 
    'MM/DD/YYYY hh:mm A', 
    'MM/DD/YYYY HH:mm'
    

If you want to hide a field dynamically, you can do so via query parameters added to the public form URL. These query parameters are prefixed with `hide_` to avoid collision with potential future query parameters.

`?hide_<field_name>` `?hide_Name` `?hide_Full+Name`

## Preview form

Before you can share the link to your form, it is advisable that you preview the form. To preview a form, click on the **Preview** button at the top of the screen to open directly to the page with your form in a new tab.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-09_at_13.07.53.png)

Alternatively, copy the private link by clicking the document icon and pasting it into your browser.

### View form data

Form data that has been filled and submitted will instantly create a new record in your database.

All submissions entered via a form will appear at the bottom of the [grid view](/user-docs/guide-to-grid-view), so long as their records are not hidden from view or sorted in a way that would limit what information shows up on submission.

## Related content

  * [View configuration options](/user-docs/view-customization).
  * [Work with gallery views](/user-docs/guide-to-gallery-view).
  * [Work with grid views](/user-docs/guide-to-grid-view).
  * [Work with kanban views](/user-docs/guide-to-kanban-view).
  * [Work with calendar views](/user-docs/guide-to-calendar-view).

