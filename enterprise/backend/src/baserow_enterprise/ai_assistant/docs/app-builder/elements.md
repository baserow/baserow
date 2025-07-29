# Baserow Documentation

Source: https://baserow.io/user-docs/elements-overview

---


## Overview

You can move elements around, link pages, and set up how they connect within your application.

> You can navigate and build with Baserow’s Application Builder using only your keyboard. [Use keyboard shortcuts for quick actions](/user-docs/baserow-keyboard-shortcuts).

Like [pages in the Application Builder](/user-docs/pages-in-the-application-builder), each element has its own settings for things like element [details](/user-docs/add-and-remove-elements), [styles](/user-docs/element-style), and [events](/user-docs/element-events). These settings change based on what kind of element it is.

When you work with elements, you have lots of choices. If you hover over one, you’ll see a toolbar with different tools. After adding an element, there’s a menu at the top with more options. You can shift, copy, or remove elements using the icons given.

## Element types

There are static elements such as the [Heading](/user-docs/application-builder-heading-element), [Columns](/user-docs/application-builder-columns-element), [Form](/user-docs/application-builder-form-element) elements, etc. They help tell people about stuff like products or portfolios.

Then, there are dynamic elements, which work in combination with a [data source](/user-docs/data-sources) to represent data in all sorts of different ways, such as the [Table](/user-docs/application-builder-table-element) element.

Here’s a list of the elements available:

Element | Description  
---|---  
[Heading](/user-docs/application-builder-heading-element) | A title displayed at the top of a page or section.  
[Text](/user-docs/application-builder-text-element) | A single line of text.  
[Link](/user-docs/application-builder-link-element) | A hyperlink to another page or URL.  
[Image](/user-docs/application-builder-image-element) | An element to display an image.  
[Text input](/user-docs/application-builder-text-input-element) | A field where users can input text.  
[Columns](/user-docs/application-builder-columns-element) | A container to organize content into multiple columns.  
[Button](/user-docs/application-builder-button-element) | A clickable button that performs an action when clicked.  
[Table](/user-docs/application-builder-table-element) | An element to display data in rows and columns.  
[Form](/user-docs/application-builder-form-element) | A container for gathering and submitting user input.  
[Choice](/user-docs/application-builder-dropdown-element) | A menu for users to select one option from a list of options.  
[Checkbox](/user-docs/application-builder-checkbox-element) | A small box for users to select an option.  
[IFrame](/user-docs/application-builder-iframe-element) | An inline frame to embed another document within the current page.  
[Login](/user-docs/application-builder-login-element) | A user login form  
[Repeat](/user-docs/application-builder-repeat-element) | Display lists or collections of data  
[Record selector](/user-docs/application-builder-record-selector-element) | Allows users to link and select related rows from other tables  
[Date time picker](/user-docs/application-builder-date-time-picker-element) | Input dates and times in your application  
[Multi-page header and footer](/user-docs/application-builder-multi-page-container) | Create a reusable container that can be used across multiple pages.  
  
## Element properties

Page formatting is designed to be flexible, so you can move elements around on the [page](/user-docs/pages-in-the-application-builder) easily.

Every element has unique properties and ways to format it based on what it’s for.

To set up an element just right, click on it. You’ll see a list of its properties on the right side of your screen.

![Element properties](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/98835a08-3c77-4d3e-b9a0-d2d431602c4b/Untitled.png)

Each element provides adaptable and user-friendly customization to tailor your page layout precisely to your needs.

Hover over any element to reveal a range of options:

  * [Duplicate an element](/user-docs/add-and-remove-elements#duplicate-element)
  * Select the parent element
  * Move an element
  * [Delete an element](/user-docs/add-and-remove-elements#remove-element-from-a-page)

![Element properties](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/da63d98d-c8ef-4999-b8b3-21549dfa4dd1/Untitled%201.png)

## Set the element data source

Setting a [data source](/user-docs/data-sources) tells an element where to get the data it needs to show. This data can be typed in by you (static data) or pulled from a database (dynamic data).

When you pick a data source for an element, you’re showing it where to look for its information.

To choose a data source for an element, click on it and check the sidebar on the right. Click on the field and select data from a list of already set up sources.

[Learn more about adding a data source](/user-docs/data-sources).

![Set the element data source](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/57bb6236-faed-4158-828c-0ad4461fee9b/Untitled%202.png)

If you need to change the data source for an element later on, simply click on the field again and select a different source from the list provided.

## Select parent element

Selecting the parent element refers to identifying and targeting the container or wrapper of a specific element.

> You can navigate and build with Baserow’s Application Builder using only your keyboard. [Use keyboard shortcuts for quick actions](/user-docs/baserow-keyboard-shortcuts).

![Select parent element](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/53a3c91d-bd66-4b8a-8205-bd22a7378d74/Untitled%203.png)

You can also click on **Elements** in the top bar to target elements based on their relationship to another element.

## Move element

To move the element up or down on the [page](/user-docs/pages-in-the-application-builder), you can use the arrows to change the element’s position.

> You can navigate and build with Baserow’s Application Builder using only your keyboard. [Use keyboard shortcuts for quick actions](/user-docs/baserow-keyboard-shortcuts).

Clicking the up arrow moves the element higher, while the down arrow shifts it lower on the page.

![Move element](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/1aea659a-bd32-43b7-91db-b2da5f4f9e2b/Untitled%204.png)

## User actions

External users can filter, sort, and search within [published applications](/user-docs/preview-and-publish-application), creating a more interactive and user-friendly experience.

For applicable elements, you can specify which fields to make filterable, sortable, and searchable for your external users.

To add filtering, ordering, and searching capabilities, click on the element and navigate to the right sidebar. There, you’ll see checkboxes to enable Filter, Sort, and Search for specific fields.

![image: filter_order_and_search_for_published_applications](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/3344732f-7eca-4ec1-b38e-e0d00a89952a/filter_order_and_search_for_published_applications.webp)

