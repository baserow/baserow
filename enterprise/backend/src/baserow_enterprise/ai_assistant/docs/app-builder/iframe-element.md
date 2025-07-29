# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-iframe-element

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Application Builder - IFrame element

The IFrame element allows you to insert custom snippets of code anywhere on your page.

In this section, we will guide you through setting up an IFrame element and explain each configuration option in detail.

## Overview

An IFrame is an HTML element used to embed another document within the current HTML document. It allows you to display content from another source without the need for the user to navigate away from the current page.

For the IFrame element, you can configure the element properties and [style](/user-docs/element-style) from the element settings.

The Application Builder allows you to bind the text to [data sources](/user-docs/data-sources). This enables the text to update dynamically based on user input or application logic.

## Add and configure IFrame elements

To add an IFrame element, access the [elements panel](/user-docs/elements-overview) and select **IFrame**.

Once added, place the IFrame wherever you want it on the [page](/user-docs/pages-in-the-application-builder). Don’t worry if it’s not perfectly positioned initially; you can always move it later.

Learn more about how to [add and remove an element from a page](/user-docs/add-and-remove-elements).

![Add and configure table elements](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/e823613f-fb69-49b3-a8ee-866ded4c2d0b/Untitled.png)

Now, you’ll configure the IFrame’s properties to make it function and look the way you want. This involves settings related to the IFrame style.

That’s it. Now the IFrame will appear.

## IFrame source type

Using IFrames can be handy for integrating content from other sources into your application seamlessly.

You can set the source as a URL or an Embed.

  * **URL:** Input the link to the external resource to be embedded. Ensure that you have control over, or trust the URL entered.
  * **Embed:** Input the raw HTML content to be embedded.

For example, if you wanted to embed a map or form on a page, you could use an IFrame to display the map without redirecting the user to an external website.

![Baserow form embed](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/5bb39ca3-6ca6-40ae-897f-2c387a25d507/Untitled%201.png)

## IFrame content

You can enter static text here. However, if you’ve connected to a [data source](/user-docs/data-sources), all the fields from the data source will also become available.

First, you need to get your embed code.

To pass dynamic data, create a corresponding field in the pre-configured [data source](/user-docs/data-sources). You can create a [text field](/user-docs/single-line-text-field) in the table and add the embed code or create a [URL field](/user-docs/url-field) with the external link.

Next, add an IFrame element to the page and link the field from the data source.

![Baserow get your embed code. ](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/cf1bd718-7203-480a-8f1c-f82c007b9dd4/Untitled%202.png)

## IFrame height (px)

The height of an IFrame element within an application can be specified in pixels (px). The maximum allowed height is 2000px.

Here’s an example of setting the iframe height to 500px:
    
    
    <iframe src="https://www.example.com" height="500" frameborder="0"></iframe>
    

