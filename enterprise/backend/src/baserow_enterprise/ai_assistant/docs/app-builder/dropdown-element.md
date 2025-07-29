# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-dropdown-element

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Application Builder - Choice element

> We renamed the Dropdown element to the Choice element to better represent its new functionality, which includes displaying a list of radio buttons or checkboxes.

The choice element lets users pick from a list of choices. It looks like a list that comes down when you click on it.

In this section, we’ll guide you through the process of setting up a choice element and explain each configuration option in detail.

![Choice element for Application Builder](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/99a6fa85-1562-485a-a9d5-1b8833a9501e/Choice%20element%20for%20Application%20Builder%20.png)

## Overview

Choice elements are versatile components used for various purposes, including creating navigation menus and selecting options from a predefined list. They offer a user-friendly way to present choices without overwhelming the interface.

> The Record Selector element enhances how users link and select related rows from other tables, making it especially useful for handling large datasets. Learn more about how to use the [Record Selector element](/user-docs/application-builder-record-selector-element).

You can configure the element properties and [style](/user-docs/element-style) from the element settings.

The Application Builder allows you to bind the text to [data sources](/user-docs/data-sources). This enables the text to update dynamically based on user input or application logic. You can also populate the options with data retrieved from data sources. This offers a dynamic way to manage options.

![Baserow choice element](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/8edd4b78-a01b-4918-917f-4c286f7c92d6/Untitled.png)

## Add and configure choice elements

To add a choice element, access the [elements panel](/user-docs/elements-overview) and select **Choice**.

Once added, place the choice element wherever you want it on the [page](/user-docs/pages-in-the-application-builder). Don’t worry if it’s not perfectly positioned initially; you can always move it later.

Learn more about how to [add and remove an element from a page](/user-docs/add-and-remove-elements).

![Add and configure table elements](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/cb156340-d793-49aa-8cc7-c3cf224da962/Untitled%201.png)

Now, you’ll configure the choice element’s properties to make it function and look the way you want. This involves settings related to choice element style.

## Choice element configuration

Choice elements are frequently used for navigation menus, or selecting options from a list. Users can choose from one of the predefined list of options you add.

The choice element has the following settings:

  * **Label:** This is a clear and concise text displayed above the choice element. It acts as a description of the choice.
  * **Default value:** This pre-selects an option from the list. If no default value is chosen, the first option is usually selected by default.
  * **Placeholder:** This provides a hint to the user about what they should select when the choice is empty.
  * **Required:** When enabled, users must choose an option from the list before continuing. This ensures they provide a necessary selection.
  * **Allow multiple values** : This option determines whether the element allows users to select multiple choices.
  * **Display** : This option controls how the element is displayed. You can choose between two options: 
    * **Dropdown** : This option presents a dropdown menu where users can select one or more options.
    * **Checkboxes** : This option displays a list of checkboxes, allowing users to select multiple options by clicking on individual checkboxes.
  * **Options:** These are the individual choices presented within the menu. Each option has two properties: 
    * **Value:** An internal identifier associated with the option. This value is typically used to store the user’s selection in your application.
    * **Name:** The text displayed to the user when presenting the options in the menu. Choose clear and concise names that accurately reflect the corresponding value.

You can populate the options with data retrieved from data sources.

