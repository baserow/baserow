# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-heading-element

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Application Builder - Heading element

A heading element defines the titles of sections within a [page](/user-docs/pages-in-the-application-builder). Heading elements help organize content and improve readability by providing structure to pages.

In this section, we’ll set up a heading element, the configuration options, and how it generally works.

## Overview

Headings are important for structuring the page and guiding users through content on the page. They establish a hierarchy, making it easier to scan information.

You can customize the [element properties and style of the heading](/user-docs/element-style) using the element settings panel on the right side of the screen.

## Add and configure heading elements

To add a heading element, click the `+` icon and select **Heading**.

Place the heading wherever you want it on the [page](/user-docs/pages-in-the-application-builder). Don’t worry if it’s not perfectly positioned initially; you can always move it later.

Learn more about how to [add and remove an element from a page](/user-docs/add-and-remove-elements).

![Add and configure table elements](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9b4430ab-5f8d-4261-acc1-72b100196f42/Untitled.png)

Now, you can configure the heading’s properties to make it function and look the way you want. This involves settings related to heading style.

## Heading levels

Baserow has several heading levels that can be customized according to your requirements.

The heading levels, ranging from `<h1>` to `<h6>` , indicate different levels of importance and hierarchy.

The `<h1>` tag represents the highest level of importance, typically used for the main title of the page, while `<h6>` represents the lowest level of importance.

![Heading level](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/39b1b36c-e6a0-41fd-a0e9-f54eb92de64b/Untitled%201.png)

## Heading text

The heading element has a text field to enter the heading text and that can be changed by clicking on it.

You can enter static text here. However, if you’ve connected to a [data source](/user-docs/data-sources), all the fields from the [data source](/user-docs/data-sources) will also become available. Select a field from the data source to fetch data dynamically.

![Heading text](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/4175c5f4-4bf8-4e56-b09a-2ea6cb4b1c0b/Untitled%202.png)

## Horizontal alignment

The horizontal alignment property controls how heading elements are positioned on the page. You can use it to achieve different visual arrangements for your headings.

Here’s a breakdown of the available alignment options:

  * **Left** : Aligns the heading to the left side of its container.
  * **Center** : Aligns the heading in the center of its container.
  * **Right** : Aligns the heading to the right side of its container.

By adjusting the horizontal alignment property, you can create a more balanced and organized layout for the page.

![Horizontal alignment](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/a9550551-377a-4864-8926-ea52a7a94f65/Untitled%203.png)

## Heading font color

You can easily modify the font color of headings in the Application Builder.

Navigate to the page where you can edit the heading you want to modify and select the heading element within the editor. Change the font color of a heading element using the Font property within a General tab.

Click on the color picker or input field next to the font color option.

Set the desired color of the heading using one of these methods:

  * **Hexadecimal color code:** Enter a six-digit code preceded by a hashtag (#), like #FF0000 for red.
  * **RGB value:** Specify the red, green, and blue values (0-255) separated by commas, like RGB (255, 0, 0) for red.
  * **Opacity:** Adjust the transparency of the chosen color using a value between 0 (fully transparent) and 1 (fully opaque).

Use a visual color picker tool to interactively choose a desired color.

Alternatively, you can inherit the default styles defined in the [theme settings](/user-docs/application-settings#theme) for a cohesive look.

![Font color](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/7f313e5b-4142-4775-9a2a-f80377b609c4/Untitled%204.png)

