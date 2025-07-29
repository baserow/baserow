# Baserow Documentation

Source: https://baserow.io/user-docs/baserow-field-overview

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Field overview

This section will guide you through the various fields available in Baserow so that you can get the most out of them. Baserow fields can be customized to fit the specific needs of your project and is a powerful tool for creating robust, interconnected databases that can streamline your workflow and improve your productivity.

Each table in a [database](/user-docs/create-a-database) consists of numerous table cells, which are important snippets of information. These table cells are arranged into columns and rows. The rows are the records. This is where information for a certain object (i.e. customer, order, etc.) is kept. The columns are the fields. The field will correspond to certain data like ID, colour and postcode.

## What is a field?

A table consists of rows and fields (columns). The rows and fields, also known as columns, are visible in the [grid view](/user-docs/guide-to-grid-view). In a table, a field is a collection of values of the same data type. Each field is a data structure that holds a defined data type.

Fields are used to maintain table relationships. You can take a field from one table and incorporate it into any other table. That’s because a table is not just a way to store your data, it’s an object that can contain other objects, each one capable of collecting data.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-06_at_09.28.18.png)

In Baserow, each [field can be configured](/user-docs/field-customization) to fit your use case. You can sort, filter, and hide the columns in a particular view without affecting other views in the table.

## Additional field actions

The following options are covered in other documentation:

  * [Field configuration options](/user-docs/field-customization)
  * [Sorting by a field](/user-docs/field-customization#sort-fields)
  * [Filtering by a field](/user-docs/filters-in-baserow)
  * [Grouping by a field](/user-docs/field-customization#group-by-field)
  * [Hiding fields and field visibility](/user-docs/field-customization#hide-field)
  * [Field descriptions](/user-docs/adding-a-field#field-description)

## Working with field types

A field can store lots of different types of data, but importantly it can only store one type of information and not a mix. Fields have different data types, such as text, numbers, dates, boolean, collaborators, select, and URL:

Field type | Description  
---|---  
[Single line text](/user-docs/single-line-text-field) | A single line text field is a type of field that allows you to input short and unique pieces of text into your table.  
[Long text](/user-docs/long-text-field) | A long text field can contain long paragraphs or multiple lines of text.  
[Link to table](/user-docs/link-to-table-field) | A link to table field creates a link between two existing tables by connecting data across tables with linked rows.  
[Number](/user-docs/number-field) | The number field is a field type that holds numerical values.  
[Rating](/user-docs/rating-field) | A rating field is used to rate your rows in order to rank or evaluate their quality.  
[Boolean](/user-docs/boolean-field) | The boolean field represents information in a binary true/false format.  
[Date](/user-docs/date-and-time-fields) | A date field lets you enter or update a date and a time into a cell.  
[Last modified](/user-docs/date-and-time-fields#last-modified-field) | The last modified field type returns the most recent date and time that a row was modified.  
[Created on](/user-docs/date-and-time-fields#created-on) | The created on field type will automatically show the date and time that a row was created by a user.  
[URL](/user-docs/url-field) | The URL field holds a single URL.  
[Email](/user-docs/email-field) | An email field is a type of field that allows input of a single email address in a cell in the right format. When you click on an email address inside of an email field, your computer’s default email client will launch with the clicked email’s To: address in the To: field.  
[File](/user-docs/file-field) | A file field allows you to easily upload one or more files from your device or from a URL.  
[Single select](/user-docs/single-select-field) | The single select field type is a field type containing defined options to choose only one option from a set of options.  
[Multiple select](/user-docs/multiple-select-field) | A multiple select field contains a list of tags to choose multiple options from a set of options.  
[Phone number](/user-docs/phone-number-field) | The phone number field will format a string of numbers as a phone number, in the form (XXX) XXX-XXXX.  
[Formula](/user-docs/understanding-formulas) | A value in each row can be calculated using a formula based on values in cells in the same row.  
[Lookup](/user-docs/lookup-field) | You can look for a specific field in a linked row using a lookup field.  
[Collaborator](/user-docs/collaborator-field) | Assign collaborators by selecting names from a list of workspace members.  
[Count](/user-docs/count-field) | The count field will automatically count the number of rows linked to a particular row in your database.  
[Rollup](/user-docs/rollup-field) | Aggregate data and gain valuable insights from linked tables.  
[Created by field](/user-docs/created-by-field) | Automatically tracks and displays the name of the collaborator who created each row within a table.  
[Last modified by field](/user-docs/last-modified-by-field) | Track decisions and actions to specific individuals for historical reference or follow-up.  
[Duration field](/user-docs/duration-field) | Stores time durations measured in hours, minutes, seconds, or milliseconds.  
[Autonumber field](/user-docs/autonumber-field) | Automatically generates unique and sequential numbers for each record in a table.  
[UUID](/user-docs/uuid-field) | Create and work with unique record identifiers within a table.  
[Last modified field](/user-docs/last-modified-field) | Create and work with unique record identifiers within a table.  
[Created on field](/user-docs/date-and-time-fields#created-on) | Create and work with unique record identifiers within a table.  
[Password field](/user-docs/password-field) | Ensure robust security measures for your data.  
[AI field](/user-docs/ai-field) | Generate creative briefs, summarize information, and more.  
  
## Computed fields

One of the most exciting features of Baserow is fields (columns) which are computed, updated, and displayed automatically. There are several types of computed fields in your table that rely on other rows or actions by users to develop the field’s value, like [link to table](/user-docs/link-to-table-field), [lookup](/user-docs/lookup-field), [last modified](/user-docs/date-and-time-fields#last-modified-field), [count](/user-docs/count-field), [rollup](/user-docs/rollup-field), [formula](/user-docs/understanding-formulas), [Created by field](/user-docs/created-by-field), [Last modified by field](/user-docs/last-modified-by-field) and [created on](/user-docs/date-and-time-fields#created-on) fields.

You set up computed fields so that they relate to other fields rather than other cells so that they apply to every row of the table and use the same computation for each row.

As a relational database, Baserow enables users to link data across tables throughout a database with fields like [link to table](/user-docs/link-to-table-field) and [lookup](/user-docs/lookup-field) fields. You can create a field in a table, then use the [link to table](/user-docs/link-to-table-field) field in another table you’ve created as a quick way to bring new data into that table.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-07-01_at_12.01.52.png)

If you would like to know more about [using fields in a database](/blog/what-is-a-field-in-a-database), then you can find out more in this article.

## Related content

  * [Create a field](/user-docs/adding-a-field)
  * [Field configuration options](/user-docs/field-customization)
  * [Working with timezones](/user-docs/working-with-timezones)
  * [Footer aggregation](/user-docs/footer-aggregation)

