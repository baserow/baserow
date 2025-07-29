# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-button-element

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Application Builder - Button element

Buttons are key for interaction in the Baserow Application Builder. They let users start actions.

We’ll show you how to set up a button and go over each setting option carefully.

## Overview

The Button element is like a trigger that lets users do something when they click it. It’s a way to make things happen with a simple click, making actions easy and quick for users.

For the button element, you can configure the element properties, [style](/user-docs/element-style), and [events](/user-docs/element-events) from the element settings.

The Application Builder allows you to bind the text to [data sources](/user-docs/data-sources). This enables the text to update dynamically based on user input or application logic.

## Add and configure button elements

To add a button element, access the [elements panel](/user-docs/elements-overview) and select **Button**.

Once added, place the button wherever you want it on the [page](/user-docs/pages-in-the-application-builder). Don’t worry if it’s not perfectly positioned initially; you can always move it later.

Learn more about how to [add and remove an element from a page](/user-docs/add-and-remove-elements).

![Add and configure button elements](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/fd21d4ec-5872-4d92-afba-d2d994adbbf5/Untitled.png)

Now, you’ll configure the button’s properties to make it function and look the way you want. This involves settings related to [button events](/user-docs/element-events), like what happens when it’s clicked, and its [style](/user-docs/element-style).

## Button horizontal alignment

There are several ways to achieve horizontal alignment for your button element within the Application Builder.

The horizontal alignment property controls how a button element is positioned within its container on the page. This helps you create a visually appealing and user-friendly page.

  * **Left:** Aligns the button to the left edge of its container.
  * **Center:** Aligns the button horizontally in the center of its container.
  * **Right:** Aligns the button to the right edge of its container.

![Button Horizontal alignment](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/7bcd5bd2-6850-40ac-9da9-a1bc1fd9e438/Untitled%201.png)

## Button width

Consider your design and user experience goals when choosing the button width.

When it comes to the appearance of buttons, you have two options: “auto” and “full width.”

  * **Auto width:** This means the button will adjust its width automatically based on the content inside. If your button text is short, the button will be narrower; if it’s longer, the button will widen accordingly.
  * **Full width:** Choosing this option means the button will stretch across the entire width of its container, regardless of the text inside. It provides a more expansive look and can be visually impactful.

![Button width](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/aadce328-9630-440e-8bf5-f47459ab979d/Untitled%202.png)

## Button color

Before publishing the application button, consider styling the buttons.

You can easily modify the color in the Application Builder.

Learn more about [element style](/user-docs/element-style).

Navigate to the page where you can edit the heading you want to modify and select the heading element within the editor. Change the color of a heading element using the property within a General tab.

Click on the color picker or input field next to the color option.

Set the desired color of the heading using one of these methods:

  * **Hexadecimal color code:** Enter a six-digit code preceded by a hashtag (#), like #FF0000 for red.
  * **RGB value:** Specify the red, green, and blue values (0-255) separated by commas, like RGB (255, 0, 0) for red.
  * **Opacity:** Adjust the transparency of the chosen color using a value between 0 (fully transparent) and 1 (fully opaque).

Use a visual color picker tool to interactively choose a desired color.

Alternatively, you can inherit the default styles defined in the [theme settings](/user-docs/application-settings#theme) for a cohesive look.

![Button color](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/a1669635-fa04-4ac9-854b-e67e6808a1fb/Untitled%203.png)

## Button events

On the right side of the page, you’ll find the **Events** tab. It has a dropdown menu where you can choose what the button will do when someone clicks on it.

A button element can perform the following actions:

  * **Show notification** : This means it can display a message or alert to the user.
  * **Open page** : Clicking the button can take the user to another page or website.
  * **Create row** : It can add a new row of data. The action requires an integration to be used.
  * **Update row** : This action allows modifying or editing existing data in a row. The action requires an integration to be used.

Learn more about [element events](/user-docs/element-events).

