# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-text-input-element

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Application Builder - Text input element

The text input element allows users to enter text data in your application.

This section will guide you through setting up a text input element and explain each configuration option in detail.

![single-line input field](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/cb67f9e5-4ab3-4c88-b4f9-4dba8df4dca8/Untitled.png)

## Overview

The text input element allows users to enter textual information. This is important for collecting various data types, including names, email addresses, URLs, and phone numbers. Text inputs are commonly used together with the [form element](/user-docs/application-builder-form-element) to create user input forms.

For the text input element, you can configure the element properties, and [customize its appearance](/user-docs/element-style) from the element settings.

## Add and configure text input elements

To add a text input element, access the [elements panel](/user-docs/elements-overview) and select **Text input**.

Once added, place the text input wherever you want it on the [page](/user-docs/pages-in-the-application-builder). Don’t worry if it’s not perfectly positioned initially; you can always move it later.

Learn more about how to [add and remove an element from a page](/user-docs/add-and-remove-elements).

![Add and configure table elements](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/e832d8d9-5673-4ddc-8be4-f01b0edeef39/Untitled%201.png)

Now, you’ll configure the text input’s properties to make it function and look the way you want.

## Text input properties

The text input element has the following common settings:

  * **Label:** A descriptive label displayed above the field.
  * **Default value:** The text pre-filled in the field when the application loads.
  * **Placeholder:** Hint text displayed within the field when empty.
  * **Required:** Determines if the user must enter a value.
  * **Multiline:** Enables users to enter text across multiple lines. You can configure the number of lines displayed initially.

The Application Builder allows you to bind the text to [data sources](/user-docs/data-sources). This enables the text to update dynamically based on user input or application logic.

By customizing these style properties, you can create text inputs that match the look and feel of the page.

## Multiline text input

A multiline input field is used to create a field where users can input multiple lines of text. It differs from a single-line input field by allowing users to enter and edit text across multiple lines.

Multiline inputs are commonly used for various purposes, such as user comments, message inputs, or any form field that requires the user to constrain text to paragraphs or longer descriptions.

![Multiline input](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/0a0ea05b-9f3a-4d31-a52d-f7bc285021c0/Untitled%202.png)

Note: Even if you limit the number of displayed lines, users can still enter more text than what’s visible. The scrollbar functionality will allow them to scroll and view/edit the entire content.

Users can type or paste text within the text area, and they can navigate and edit the text using keyboard shortcuts and mouse clicks.

