# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-repeat-element

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Application Builder - Repeat element

A repeat element allows you to show a list within a [page](/user-docs/pages-in-the-application-builder) by repeating the elements for each result in the data source. It allows you to repeat a set layout for each item in a container, making it easier to manage large amounts of similar data.

In this section, we’ll set up a repeat element, the configuration options, and how it generally works.

## Overview

Repeat elements allow you to display lists or collections of data. Instead of manually creating multiple instances of similar elements, repeat elements can dynamically generate as many instances as needed based on the data source.

Using repeat elements ensures consistency across the application. When you update the design or functionality of a repeat element, the changes are automatically applied to all instances. This makes maintenance easier and reduces the risk of inconsistencies.

You can customize the [element properties and style of the element](/user-docs/element-style) using the element settings panel on the right side of the screen.

## Hierarchy using the Repeat element

You can create two types of hierarchies using the Repeat element:

  * **Root-level collection element** : This type of element is associated with a multiple-row [data source](/user-docs/data-sources) but does not have a multiple-valued property. It allows you to create a primary collection that can iterate over data rows.
  * **Nested collection element** : This type of element does not require a [data source](/user-docs/data-sources) but instead uses a multiple-valued property. It is embedded within another collection element, allowing you to display a hierarchy, such as a list of departments with each containing a nested list of employees or categories with nested products for an e-commerce store.

![Hierarchy using the Repeat element](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/6479b9ca-d9ce-4523-a2b2-cedada4ca1ba/nested_collection_elements.webp)

## Add and configure repeat elements

To add a repeat element, click the `+` icon and select **Repeat**.

Place the element wherever you want it on the [page](/user-docs/pages-in-the-application-builder). Don’t worry if it’s not perfectly positioned initially; you can always move it later.

Learn more about how to [add and remove an element from a page](/user-docs/add-and-remove-elements).

Now, you can configure the element’s properties to make it function and look the way you want. This involves settings related to repeat style and [adding child elements](/user-docs/add-and-remove-elements) to the repeat element.

![Baserow app builder repeat element](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/0ee7d1fb-09f2-45c5-a6db-f58326dfb831/Application%20Builder%20-%20Repeat%20element%20.png)

## Repeat data source

> To list rows in the repeat list, set the [data source](/user-docs/data-sources) service type as _List multiple rows_. Learn more about data sources and how to configure them.

After adding a repeat element to the page from **Elements** , you need to select the [data source](/user-docs/data-sources) which you want to import your data from. This is done from the **General** tab of the element settings.

![Repeat element screenshot](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/0f4b9ce7-c200-4e69-ba10-cf92bc4bef49/Repeat%20element.png)

## Repeat items per page

You can choose how many items appear in the list by default. The field must be an integer and must be less than or equal to 100.

If there are more items to display than the defined number, a **Show more** button will be added at the end of the list, allowing the user to expand the list and view the additional items.

## Repeat element orientation

This setting controls how repeated elements are arranged on the screen. You can choose between two orientations:

  * **Vertical:** Elements will be stacked on top of each other.
  * **Horizontal:** Elements will be displayed in rows from left to right.

When choosing horizontal orientation, you can further define the number of elements displayed per row for different device types. This allows you to customize the layout for optimal viewing on various screen sizes.

**Properties of items per row:**

  * **Per device type:** You can set a different number of items per row for each device type (e.g., mobile, tablet, desktop).
  * **Integer value:** The number of items must be a whole number (1, 2, 3, etc.).
  * **Range:** The number of items must be between 1 and 10 (inclusive).

![Repeat element horizontal screenshot](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/4f372355-aae8-4044-b3cc-1097d0c2ee44/Repeat%20element%20-%20vertical.png)

## User actions

External users can filter, sort, and search within [published applications](/user-docs/preview-and-publish-application), creating a more interactive and user-friendly experience.

For the repeat element, you can specify which fields to make filterable, sortable, and searchable for your external users.

To add filtering, ordering, and searching capabilities, click on the repeat element and navigate to the right sidebar. There, you’ll see checkboxes to enable Filter, Sort, and Search for specific fields.

![image: filter_order_and_search_for_published_applications](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/40f9ce8a-e81b-4740-a3b0-b7bbc635a37d/filter_order_and_search_for_published_applications.webp)

