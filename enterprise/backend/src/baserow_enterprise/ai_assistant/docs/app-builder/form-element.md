# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-form-element

---


## Overview

For the form element, you can configure the element properties, [style](/user-docs/element-style), and [events](/user-docs/element-events) from the element settings.

The form layout is customizable and you can have any number of fields, specifying the type of each field.

For example, if you have a job board, each job detail page can contain a form through which visitors can apply for that job.

The Application Builder allows you to bind the text to [data sources](/user-docs/data-sources). This enables the text to update dynamically based on user input or application logic.

![Form element](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2496bc41-709f-4530-bf3b-84fe5c31e922/Untitled.png)

## Add and configure form elements

To add a form element, access the [elements panel](/user-docs/elements-overview) and select **Form**.

Once added, place the form wherever you want it on the [page](/user-docs/pages-in-the-application-builder). Don’t worry if it’s not perfectly positioned initially; you can always move it later.

Learn more about how to [add and remove an element from a page](/user-docs/add-and-remove-elements).

![Add and configure table elements](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/0fe1dc92-f78e-4945-908b-df6850671e85/Untitled%201.png)

Now, you’ll configure the form’s properties to make it function and look the way you want. This involves settings related to form events (like what happens when it’s clicked) and its style.

## Form element types

Now, let’s see what element types are available:

  * **Text input** \- an input field that requires the user to type in the value.
  * **Dropdown** – a dropdown where users can choose from one of the predefined list of options. For the dropdown element, you will add all the available options**.**
  * **Checkbox** \- a checkbox field with a yes/no value.

## Form submit button

In the General tab, you customize the submit button and button color.

You can enter static text as the _Submit button_ value. However, if you’ve connected to a [data source](/user-docs/data-sources), all the fields from the data source will also become available for your choice.

![Submit button](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b6f3848b-538f-4261-9cb5-bf92dc33d03f/Untitled%202.png)

## Form button color

You can easily modify the color in the Application Builder.

Navigate to the page where you can edit the heading you want to modify and select the heading element within the editor. Change the color of a heading element using the property within a General tab.

Click on the color picker or input field next to the color option.

Set the desired color of the heading using one of these methods:

  * **Hexadecimal color code:** Enter a six-digit code preceded by a hashtag (#), like #FF0000 for red.
  * **RGB value:** Specify the red, green, and blue values (0-255) separated by commas, like RGB (255, 0, 0) for red.
  * **Opacity:** Adjust the transparency of the chosen color using a value between 0 (fully transparent) and 1 (fully opaque).

Use a visual color picker tool to interactively choose a desired color.

Alternatively, you can inherit the default styles defined in the [theme settings](/user-docs/application-settings#theme) for a cohesive look.

![Button color](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/33255c0e-ca8e-4350-9768-fb3bc70ef82d/Untitled%203.png)

## Form events

In the Events tab, you can set where it’s going to be sent. To set the form’s destination, you have the following options:

  * **Show notification** : This means it can display a message or alert to the user.
  * **Open page** : Clicking the button can take the user to another page or website.
  * **Create row** : It can add a new row of data. The action requires an integration to be used.
  * **Update row** : This action allows modifying or editing existing data in a row. The action requires an integration to be used.

Learn more about [element events](/user-docs/element-events).

