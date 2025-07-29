# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-image-element

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Application Builder - Image element

Adding visual elements can greatly enhance user experience. In this section, we’ll walk you through setting up a display image element and explain each configuration option in detail.

## Overview

For the image element, you can configure the element properties and [style](/user-docs/element-style) from the element settings.

Setting up a display image element involves a few key configurations:

  * **Image file:** Choose the image you want to display via upload or URL.
  * **Alt text:** This is a brief description of the image.
  * **Alignment:** Position the image where you want it on the page – left, right, or center.
  * **Image size:** Adjust the width and height of the image in pixels. You can choose specific dimensions or use a percentage to scale the image proportionally.

![Baserow Application Builder - Image element](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/dd35bc3f-f94a-494d-a55d-4f2c0c4c45bf/Untitled.png)

## Add and configure image elements

To add an image element, access the [elements panel](/user-docs/elements-overview) and select **Image**.

Once added, place the image wherever you want it on the [page](/user-docs/pages-in-the-application-builder). Don’t worry if it’s not perfectly positioned initially; you can always move it later.

Learn more about how to [add and remove an element from a page](/user-docs/add-and-remove-elements).

![Add and configure table elements](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/910666b3-25bb-48d3-80d6-dcfce5681e58/Untitled%201.png)

Now that you’ve added the image, it’s time to customize its appearance and functionality. This is where image properties come in, including those related to [style](/user-docs/element-style).

## Image file

When you want to add an image to a page, you have two options: uploading it directly from your device, or providing the web address (URL) where the image is stored online.

### Upload from device

Uploading works best for pictures you have or manage yourself. It’s when you pick an image file from your computer, phone, or another device.

To upload an image directly from your device, click the **Upload** button. This will open a file explorer window on your device.

Locate the desired image file and select it. The Application Builder will then upload the image and make it available for use on the page.

### By URL

If the image you want to use is stored online, you can link to it instead of uploading it. Linking is preferable when the image is hosted elsewhere.

  * Click **URL**.
  * Paste the complete web address (URL) of the image you want to display in this field.
  * Ensure the image is publicly accessible online. The Application Builder will attempt to fetch the image from the provided URL and display it on the page.

The Application Builder allows you to bind the URL to [data sources](/user-docs/data-sources). This enables the URL to update dynamically based on user input or application logic. This is helpful for referencing existing images stored elsewhere.

## Image alt text

Image alt text, which is short for “alternative text,” is important for accessibility and search engine optimization (SEO).

An image alt text provides a textual description of the image for users who may not be able to see it. The alt text is displayed if the image fails to load properly in a web browser and read aloud by screen readers for the visually impaired, ensuring everyone can understand the image’s purpose.

The Application Builder allows you to bind the text to [data sources](/user-docs/data-sources). This enables the text to update dynamically based on user input or application logic.

## Image element horizontal alignment

Horizontal alignment refers to placing an image to the left, center, or right side of its parent element, which can be the entire page or a specific section.

  * **Left:** The image will be positioned flush against the left edge of its container.
  * **Center:** The image will be horizontally centered within its container.
  * **Right:** The image will be positioned flush against the right edge of its container.

![Horizontal alignment](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/354c98bb-cdac-4796-9134-aaf1e73859df/Untitled%202.png)

## Control image size

This helps you manage how images are displayed on the page. By setting the image size appropriately, you can ensure they fit seamlessly without appearing stretched or distorted.

There are two options to control image size:

  * **Max width (percentage):** This determines the image’s maximum width relative to its container. This ensures images don’t overflow their container horizontally. The percentage value must be between 0 and 100, to reflect the desired portion of the container’s width the image should occupy. Percentages provide flexible layouts that adapt to different screen sizes.
  * **Max height (pixels):** This defines the image’s maximum height in pixels. This prevents large images from disrupting the layout. The value must be between 5 and 3000 pixels to constrain the image’s vertical dimension. Pixels provide a fixed value for specific height requirements.

## Image constraint

Constraining images ensures a consistent visual experience and prevents unintended layout issues.

For image element, here are the constraints:

  * **Extend to max width** : This means the image will stretch horizontally as much as it can without distorting its height. It fills the available space from left to right.

  * **Contain** : Contain means the image will fit entirely within its container. This option is unavailable while limiting the height of the image. If the image has a maximum height set, the image won’t be able to adhere to it while containing.

  * **Cover** : Cover means the image will expand or shrink to cover the entire container, maintaining its aspect ratio. This may result in parts of the image being cropped if it doesn’t perfectly fit the container’s dimensions. This option is unavailable when the max height is not set.

