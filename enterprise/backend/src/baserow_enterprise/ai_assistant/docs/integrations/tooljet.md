# Baserow Documentation

Source: https://baserow.io/user-docs/tooljet

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Configure Baserow in ToolJet

Use 1000s of open source triggers and actions across 900+ apps or write custom code to integrate any app or API in seconds.

[ToolJet](https://www.tooljet.com/) is an open-source low-code platform that allows you to quickly build applications and perform operations in your Baserow database. You can connect ToolJet with more than 30 different data sources, including Baserow.

## What you’ll need

  * A Baserow account
  * A free account on [ToolJet Cloud](https://www.tooljet.com/) or run on your [local machine](https://docs.tooljet.com/docs/setup/)

You need to authenticate with your Baserow database API token before you can connect the CRM data to ToolJet.

For detailed information on how to create a database token, [visit our documentation](/user-docs/personal-api-tokens).

## Supported operations

  * List fields
  * List rows
  * Get row
  * Create row
  * Update row
  * Move row
  * Delete row

### Parameters

  * [Table ID](/user-docs/database-and-table-id)
  * Row ID
  * Before ID - The row will be moved before the entered ID. If not provided, then the row will be moved to the end
  * Records

You can get your database parameters from the Baserow [API documentation](/api-docs/).

## Connect Baserow to ToolJet

Select the ‘Sources’ tab in the app builder’s left sidebar to access the Datasource manager in ToolJet.

Click the **‘+ add data source’** button to add a datasource:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/e381df45-b524-4411-bada-c2d9b163e85b/image.png)

Select Baserow from the modal that pops up as the data source that you want to add:

![https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/5b11971d-42f5-4dbd-943e-11e45d7376cc/Screenshot_2022-10-26_at_08.40.47.png](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/5b11971d-42f5-4dbd-943e-11e45d7376cc/Screenshot_2022-10-26_at_08.40.47.png)

Input your Baserow API token in ToolJet and select whether it’s **Baserow Cloud** (hosted version of Baserow) or **Self-Host**. For the **[self-hosted](/docs/index#installation)** option, a base URL is required to connect.

Then, click the **Save** button to save the datasource:

![https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/7e80259c-ef06-44b0-896c-223af2459ae1/Screenshot_2022-10-26_at_09.09.39.png](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/7e80259c-ef06-44b0-896c-223af2459ae1/Screenshot_2022-10-26_at_09.09.39.png)

The fields that are marked as `encrypted` will be encrypted before saving them to ToolJet’s database.

## Build Queries

To create a new query, click on the `+` icon of the query editor.

> A query is a request for data or information from a database table or combination of tables.

Select the Baserow datasource:

![https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b2a075a9-cd3e-4a99-b860-f7205b63ae31/Screenshot_2022-10-27_at_09.42.26.png](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b2a075a9-cd3e-4a99-b860-f7205b63ae31/Screenshot_2022-10-27_at_09.42.26.png)

Create a new `Baserow` query and select an operation from the operations dropdown and input the required parameters.

### List fields

This query lists all the fields in a table.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/de8e2aeb-277c-431e-996e-46188f868027/Untitled.png)

### List rows

This query will get the list of all the rows from the tables in the Baserow.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/41dfd463-7e4c-4fae-b337-bef15ee099ed/Untitled%201.png)

### Get row

This query retrieves all the rows in a table.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2b54a28c-d924-4eba-ac3a-c0863c4ebaa1/Untitled%202.png)

### Create row

This query will create row(s) in the table with input from fields.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/816c5275-0cbf-471d-b855-ba21b2fd5504/Untitled%203.png)

### Update row

This query will update row(s) in the table with input from fields.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2b8ba4c6-9ba1-45af-88bd-81e597468c73/Untitled%204.png)

### Move row

This query will move row(s) in the table.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/4856378e-7d29-4e6b-b7e6-1c2c6b65a6b5/Untitled%205.png)

### Delete row

This query will delete row(s) in the table.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9121bfd1-ab8c-4e3a-b55e-029e1d284ad7/Untitled%206.png)

> For a more detailed tutorial, refer to this article on [How to Build a Custom CRM System with Baserow and ToolJet](/blog/how-to-build-a-crm-system-with-baserow-and-tooljet).

