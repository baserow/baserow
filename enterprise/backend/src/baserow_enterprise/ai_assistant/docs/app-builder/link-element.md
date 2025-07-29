# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-link-element

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Application Builder - Link element

Links are essential for smooth navigation and user interactions in an app. They help users move between pages, start actions, or reach outside websites.

We’ll explore how to set up links well so they can connect to pages inside the app and to external sites.

## Overview

For the link element, you can configure the element properties, and [style](/user-docs/element-style) from the element settings.

The Application Builder allows you to bind the text to [data sources](/user-docs/data-sources). This enables the text to update dynamically based on user input or application logic.

## Add and configure link elements

To add a link element, access the [elements panel](/user-docs/elements-overview) and select **Link**.

Once added, place the link wherever you want it on the [page](/user-docs/pages-in-the-application-builder). Don’t worry if it’s not perfectly positioned initially; you can always move it later.

Learn more about how to [add and remove an element from a page](/user-docs/add-and-remove-elements).

![Add and configure table elements](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/23b2f00d-e440-4629-9392-04e3d1b6fa7e/Untitled.png)

Now, you’ll customize the link’s behavior and appearance by configuring its properties. This includes options for linking to specific actions within the application.

## Linking to pages

The Application Builder allows you to create links that, when clicked, take users to a designated page within your application.

You can control whether the linked page opens in the same browser tab (replacing the current content) or in a new tab altogether. Choosing the right option depends on your application’s structure and user flow. Here’s a quick guideline:

  * **Open in same tab** : When you click a link within a page, the new content replaces the current one in the same browser tab. This keeps your browsing experience focused on a single window.
  * **Open in new tab** : Clicking a link within the page opens the linked content in a new browser tab. This allows you to keep the original content accessible while viewing the new one separately.

![Baserow Link Open in...](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/06d32e8c-84dc-485e-a2ed-85497374accc/Untitled%201.png)

## Navigate to a page

This feature lets you link to a different page in the application. When you navigate to a page, you’re moving to that place in the application where you can view content or do things.

### Navigate to a path

Navigating to a path is about moving to a specific location within the application, which is identified by its path in the application’s structure.

You need to first add a parameter via `:parameter` . [Path parameters](/user-docs/application-builder-page-settings#path-parameters) can be used to load data, depending on the provided parameter dynamically.

The content will be generated automatically on that page depending on which specific detail the user has navigated to the detail page from.

You can also do the same for a link type in the field configuration on a table element.

### Navigate to a custom URL

Navigating to a custom URL means going to a web address that is specifically designed or created for a particular purpose, often outside of the standard paths predefined by the application.

To link to an external website, input the URL into the link field using the following format `https://www.example.com`.

### View row details

You can link to an internal page and set it to open a separate page within your Baserow application. For example, when the user clicks on a button, you want to display the row details.

  1. **Map row ID:** Ensure the row ID field in the [data source](/user-docs/data-sources) configuration is properly mapped. This will be used to identify the specific row when displaying details.

> Determine the [data source](/user-docs/data-sources) that contains the information you want to show. This should be the same [data source](/user-docs/data-sources) that provides the details on the current page, or it could be a different one.

  2. **Create a link:**

     * Navigate to the element settings for the button or link you want to use to access the details page.
     * Open the **General** tab.
     * Locate the **Navigate to** dropdown menu.
     * Select the dynamic page that displays the detailed information for a specific row.

![Link row to a details page](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/7b858a00-baa9-437a-8e8c-3f3de8434434/Untitled%202.png)

That’s it. Now when the user clicks on a particular button, they will be taken to the page with the specific details.

That’s it. Now when the user clicks on a particular button, they will be taken to the page with the specific details.

## Link variant

A link variant refers to the style or type of link used.

When you select the Button variant, you can consider the design and user experience goals by choosing the button width.

When it comes to the appearance of buttons, you have two options: “auto” and “full width.”

  * **Auto width:** This means the button will adjust its width automatically based on the content inside. If the button text is short, the button will be narrower; if it’s longer, the button will widen accordingly.
  * **Full width:** Choosing this option means the button will stretch across the entire width of its container, regardless of the text inside. It provides a more expansive look and can be visually impactful.

![Link to a details page](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b75c9700-e59c-4e5e-97ad-8c2434f908c4/Untitled%203.png)

## Link horizontal alignment

You can horizontally align a link element using the horizontal alignment property. This will align the link on the page.

  * **Center:** Aligns the link text in the middle of its container horizontally.
  * **Left:** Aligns the link text to the left edge of its container.
  * **Right:** Aligns the link text to the right edge of its container.

## Link button color

The color of a button refers to the visual appearance of the button itself. You can easily modify the link color in the Application Builder.

Navigate to the page where you can edit the button you want to modify and select the link element within the editor. Change the color using the Button color property in a General tab.

Click on the color picker or input field next to the color option.

Set the desired color of the heading using one of these methods:

  * **Hexadecimal color code:** Enter a six-digit code preceded by a hashtag (#), like #FF0000 for red.
  * **RGB value:** Specify the red, green, and blue values (0-255) separated by commas, like rgb(255, 0, 0) for red.
  * **Opacity:** Adjust the transparency of the chosen color using a value between 0 (fully transparent) and 1 (fully opaque).

Use a visual color picker tool to interactively choose a desired color.

Alternatively, you can inherit the default styles defined in the [theme settings](/user-docs/application-settings#theme) for a cohesive look.

![Link button color](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9ecea232-7a25-4d26-943c-4d4d32294ce7/Untitled%204.png)

