# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-table-element

---


## Overview

For the table element, you can configure the element properties and [style](/user-docs/element-style) from the element settings.

To get started, you need to connect a pre-configured [data source](/user-docs/data-sources) to fetch data from data sources and display it on the table.

As soon as you add a table element to the page, the element settings will become available and you can start setting it up.

![Baserow Application Builder table element](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/f6b10d57-f288-46d9-b83e-ffdaf2c8fb79/Untitled.png)

## Add and configure table elements

To add a table element, access the [elements panel](/user-docs/elements-overview) and select **Table**.

Once added, place the table wherever you want it on the [page](/user-docs/pages-in-the-application-builder). Don’t worry if it’s not perfectly positioned initially; you can always move it later.

Learn more about how to [add and remove an element from a page](/user-docs/add-and-remove-elements).

![Add and configure table elements](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/56fa9be7-100e-4b96-bf0e-c32000d89de2/Untitled%201.png)

Now, you’ll configure the table’s properties to make it function and look the way you want. This involves settings related to table style.

## Table data source

> To list rows in the table, set the [data source](/user-docs/data-sources) service type as _List rows_. Learn more about data sources and how to configure them.

After adding a table element to the page from **Elements** , you need to select the [data source](/user-docs/data-sources) which you want to import your data from. This is done from the **General** tab of the element settings.

![Data source](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/69f11760-4aee-4803-8a08-dc3196d65a73/Untitled%202.png)

As soon as you select a **Data source** , you’ll see the Fields configuration appear below.

## Table items per page

You can choose how many items appear in the list by default. The field must be an integer and must be less than or equal to 100.

If there are more items to display than the defined number, a **Show More** button will be added at the end of the list, allowing the user to expand the list and view the additional items.

## Table fields

This is where you configure how the data will be mapped to a table to specify how exactly you want to display your data.

You can configure some additional parameters for the table element and map the element fields to the data source to specify what data needs to be displayed and how.

For each field, you can add a Name, Type, Value, and Link text. You can also configure the position of the fields.

### Add a new field

You can add new fields using the **Add field** button. After adding the field, you need to specify its Name, Type, Value, and Link text.

Fields can have the following settings:

  * Name – a title for the column
  * Type
  * Value
  * Link text
  * Navigate to
  * Parameter

![Add a new field](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/55181490-ee96-4b27-832c-f8408df90631/Untitled%203.png)

### Field name

Here you set the title of the field. The name of the field can be modified as needed.

### Field type

Choosing the appropriate field type ensures your table data is stored and displayed effectively. The table element supports the following field types:

  * **Text** : This is the most versatile type, suitable for any textual content, including names, descriptions, or short paragraphs.
  * **Link** : Use this type to create clickable links within your table cells. When clicked, these links navigate users to external websites or internal pages within your application.
  * **Boolean** : This type represents a true/false value. It’s ideal for capturing binary data like “Active/Inactive” or “Yes/No” flags.
  * **Tags** : This type allows users to assign labels or categories to table cells. Tags are commonly used for filtering, sorting, or grouping data based on these labels.

### Field value

If the Text type is selected, you can also set the value of the field.

You can enter a specific value for the selected field so that the rows display that value.

You can enter static text here. However, if you’ve connected to a [data source](/user-docs/data-sources), all the fields from the data source will also become available for your choice.

![Enter value](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/71fac19d-55d7-414e-9263-67e52c8222bf/Untitled%204.png)

### Field link text

If the Link type is selected, you can also set the link text of the field.

Similar to the text value, you can enter static text here. However, if you’ve connected to a [data source,](/user-docs/data-sources) all the fields from the data source will also become available for your choice.

![Enter Link text](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/8beb966d-9e74-4631-aef9-31ea1ba5c698/Untitled%205.png)

### Navigate to

If the Link type is selected, you can also link to an internal page or custom URL through a button.

![Navigate to](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/883b4278-e114-43aa-a9dc-9b85e0ece9c2/Untitled%206.png)

### Link row to a details page

If the Link type is selected, you can link to an internal page through a button and set it to open a separate page within the Baserow application to view the details of a row.

> In the detail page, you should link to the same data source that the table to which you want to connect the details is linked to.

For example, let’s say you have a list of projects in a table. When the user clicks on the link associated with a specific project, you want to display this project’s details.

You need to first add a parameter via `:parameter` . Path parameters can be used to load data, depending on the provided parameter dynamically. Then map the row ID in the data source configuration.

![Link row to a details page](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/fd769e3e-d098-4157-95c7-5338cbd9b6c2/Untitled%207.png)

To link to a dynamic page, go to the element settings and open the General tab. From the **Navigate to** dropdown menu, set the detail page to which the table items are supposed to be linked.

![ink to a dynamic page](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/09d9e959-8e99-4a42-aa8c-bdf04e64eb0a/Untitled%208.png)

That’s it. Now when the user clicks on a particular link associated with a row, they will be taken to the page with the details of the row.

The content for each row will be generated automatically on that page depending on which row the user has navigated to the detail page from.

You can also do the same for a Button element.

### Delete a field

![Delete a field](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/92c43c91-7342-4dd7-9fa4-8a3dd0353009/Untitled%209.png)

## Button color

You can easily modify the color in the Application Builder.

The color of a button refers to the visual appearance of the button itself.

You can configure the color of the **Show more** button to show more items in the list.

Navigate to the page where you can edit the heading you want to modify and select the heading element within the editor. Change the color of a heading element using the property within a General tab.

Click on the color picker or input field next to the color option.

Set the desired color of the heading using one of these methods:

  * **Hexadecimal color code:** Enter a six-digit code preceded by a hashtag (#), like #FF0000 for red.
  * **RGB value:** Specify the red, green, and blue values (0-255) separated by commas, like RGB (255, 0, 0) for red.
  * **Opacity:** Adjust the transparency of the chosen color using a value between 0 (fully transparent) and 1 (fully opaque).

Use a visual color picker tool to interactively choose a desired color.

Alternatively, you can inherit the default styles defined in the [theme settings](/user-docs/application-settings#theme) for a cohesive look.

![Button color](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/c4821c54-88e8-4003-8de5-c2de03937b25/Untitled%2010.png)

## Sort fields

You can manually reorder the fields with the drag-and-drop functionality.

![Sort fields](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/fa3d40c5-ac29-4b34-835c-005aa7240ce0/Untitled%2011.png)

## Table element orientation

This setting controls how rows in the table element are arranged on the screen. You can define how the fields are displayed for different device types. This allows you to customize the layout for optimal viewing on various screen sizes.

You can choose between two orientations:

  * Vertical: Fields will be stacked on top of each other.
  * Horizontal: Fields will be displayed in rows from left to right.

## User actions

External users can filter, sort, and search within [published applications](/user-docs/preview-and-publish-application), creating a more interactive and user-friendly experience.

For the table element, you can specify which fields to make filterable, sortable, and searchable for your external users.

To add filtering, ordering, and searching capabilities, click on the table element and navigate to the right sidebar. There, you’ll see checkboxes to enable Filter, Sort, and Search for specific fields.

![image: filter_order_and_search_for_published_applications](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/1b4b3701-6795-404b-86ef-2cfa24391ec0/filter_order_and_search_for_published_applications.webp)

