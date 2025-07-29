# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-record-selector-element

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Application Builder - Record selector element

The Record Selector simplifies linking and selecting rows from related tables. This is useful when selecting any of the thousands of rows from a related table to populate a link row field.

In this section, we’ll provide detailed instructions and best practices for using the Record Selector element in the Application Builder.

![Baserow Record selector element](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9349ad70-8f47-4366-b169-c7faed797819/record_selector_element.webp)

## Overview

The Record Selector enables you to populate a link row field by selecting from rows in another table. This is ideal for scenarios where dynamic data connections are needed, such as assigning roles, linking tasks, or selecting categories from a related dataset.

The Record Selector handles thousands of rows using dynamic data loading, ensuring fast performance even for large datasets.

You can configure the element properties and [style](/user-docs/element-style) from the element settings.

The Application Builder allows you to bind the text to [data sources](/user-docs/data-sources). This allows the text to update dynamically based on user input or application logic. You can also populate the options with data retrieved from data sources. This offers a dynamic way to manage options.

## Add the record selector to an application

To add a record selector element, access the [elements panel](/user-docs/elements-overview) and select **Record selector**.

Once added, place the record selector element wherever you want it on the [page](/user-docs/pages-in-the-application-builder). Don’t worry if it’s not perfectly positioned initially; you can always move it later.

Learn more about how to [add and remove an element from a page](/user-docs/add-and-remove-elements).

Then, you can configure the record selector element’s properties to make it function and look the way you want. This involves settings related to the record selector element style.

## Configure the Record Selector settings

Once the element is added, configure its properties in the settings panel. You can populate the options with data retrieved from data sources. The dropdown dynamically reflects changes in the linked table, ensuring real-time updates.

The following settings are available:

  * **Select records from** : Choose the [data sources](/user-docs/data-sources) you want to pull records from. Example: Job roles or Departments.
  * **Items per page** : Define how many rows are displayed in the selector view. Example: 20. This number must be greater than or equal to 5 but less than or equal to 100.
  * **Option name suffix** : Add a suffix to distinguish rows when displayed in the dropdown. Example: combining multiple data fields like “Company - [Value]”.
  * **Label** : Enter a clear label for the field. Example: “Select one or more roles”.
  * **Placeholder** : Add placeholder text to guide users on what to do. Example: “Make a selection”.
  * **Default value** : Pre-define the field’s initial value using a specific data source or default logic. Example: Default to the first row. If you don’t define a default value, the field will remain empty until the user selects a row.
  * **Allow multiple values** : Toggle this option if you want users to select more than one row.
  * **Required** : Check this box if the field must be completed before submission.
  * **User actions** : You can configure search functionality for external users by selecting relevant properties under the **User actions** section.

## User actions

For each element, you can specify which fields to make searchable for external users to give end-users more control to search within the [published application](/user-docs/preview-and-publish-application).

To add searching capabilities, click on the element and navigate to the right sidebar. There, you’ll see checkboxes to enable Search for specific fields.

![Record selector element - User actions](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/0c1c59c5-06db-4212-b52a-ef7003823a2a/record_selector_element_user_actions.webp)

This creates a more interactive and user-friendly experience.

![Configure the Baserow Record Selector Settings](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/868ff5a8-d4f3-4184-b945-1e8a7f289349/Screenshot%202024-12-10%20at%2013.17.39.png)

