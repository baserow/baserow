# Baserow Documentation

Source: https://baserow.io/user-docs/make

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Configure Baserow in Make

Make allows you to create custom workflows that can perform actions in response to a trigger. Baserow can be easily connected to over 1000 apps and services, allowing you to automate repetitive tasks without writing code.

## What you’ll need

  * A Baserow account
  * A free [Make](https://www.make.com/) account

## Supported Operations

**Triggers**

  * Watch Created Rows \- Trigger when new rows are created.

**Actions**

  * Create a Row \- Creates a new row.
  * Get a Row \- Finds a single row in a given table.
  * Delete a Row \- Deletes an existing row.
  * Update a Row \- Updates an existing row.
  * Make an API Call \- Performs an authorized API call.

**Searches**

  * List Rows \- Finds a page of rows in a given table.

## Create a Baserow Database token

Before connecting to Make, you must authenticate with your Baserow [database token](/user-docs/personal-api-tokens).

> ⚠️ Database tokens provide similar functionality to login credentials, but they provide additional security and flexibility. A token, like your username and password, should be kept secure and handled with the utmost confidentiality. Do not share it with others or expose it.

  1. Log in to your Baserow account.

  2. Click on your account/profile in the top left corner, then navigate to “**Settings”** → “**Database tokens”.**

  3. Click on the ‘**Create token +’** button

  4. Enter a name for the token and select an existing workspace

  5. Click on the ‘**Create token’** button to create a new token for the selected workspace and for the authorized user.

![create a Baserow Database token](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/33e70ffb-482e-402e-aa5a-94f61b9014ec/Make%20Token.webp)

  6. Copy the database token to a safe place.

You have created a database token successfully.

## Create a connection using a database token

To automate with most apps in Make, you must first create a connection. Through this connection, Make communicates with the third-party service according to the settings of your specific scenario.

  1. Log in to your Make account, open the Baserow module scenario, and click the ”**Add”** button next to the  _Connection type_ field.

  2. Optional: In the  _Connection name_ field, enter a name for the connection. A default connection name is provided. You can change it if you want.

  3. Enter your Baserow API URL. Find your **Baserow API URL** in your [API documentation](/api-docs). If you are using cloud version [baserow.io](/), the default URL is `https://api.baserow.io`, otherwise, replace the URL with your self-hosted URL.

  4. Enter the token copied in the section, Create a Database token.

![Create a connection using a database token](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/bba6a763-d4f8-4d3b-9b8f-c25fb7e67e82/Screenshot_2023-03-17_at_06.33.32.png)

  5. Click **Save** to create a connection.

The connection has been established successfully. You can now edit your scenario to add Baserow modules.

> You can manage your connections in the **Connections** section in Make. Here you can see which permissions Make has for your Baserow account and rename, reauthorize, or delete existing connections.

## Baserow Modules

You can watch, create, get, update, list and delete rows, and call APIs using the following modules.

### Watch Created Rows

Returns all newly created or updated rows in a table.

  1. Add the **Watch Created Rows** module to your Make scenario.

  2. Configure the trigger

Configuration |   
---|---  
Connection | Create a connection using database token  
Table ID | Enter (or map) your Baserow [Table ID](/user-docs/database-and-table-id) in which you want to watch rows created. You can find the ID by clicking on the three dots next to the table in the database. It’s the number between brackets.  
  
![Watch Created Rows](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/58b5f301-f5f2-4237-bb31-0a445dc308cb/Screenshot_2023-03-17_at_06.58.03.png)

  3. Click “**OK** ” to save this module and “**Run once** ” to test the connection.

Every time a new row is created, the **Watch Created Rows** module in your Make scenario is triggered and returns the row details.

> Optionally, use the Webhook module to trigger when the webhook receives data. For more information on how to create a webhook in Baserow, see the [support documentation](/user-docs/webhooks).

### Create a Row

Creates a new row in a Baserow.

  1. Add the **Create a Row** module to your Make scenario.

  2. Configure the action

Configuration |   
---|---  
Connection | Create a connection using database token  
Table ID | Enter (or map) your Baserow [Table ID](/user-docs/database-and-table-id) in which you want to create a row. You can find the ID by clicking on the three dots next to the table in the database. It’s the number between brackets.  
Row data | Enter (or map) values in the fields. See Baserow’s [guide to permitted field types](/user-docs/baserow-field-overview).  
  
> Toggle the map option to retrieve items from a source module and then map in the settings of the **Create a Row** module. Click the field you want to map an item from a previous module. This will open a mapping panel with all items and sample values available for mapping from the preceding modules in the scenario.

  3. Click “**OK** ” to save this module and “**Run once** ” to test the connection.

### Get a Row

Retrieves a single row in a given table by its ID.

  1. Add the **Get a Row** module to your Make scenario.

  2. Configure the action

Configuration |   
---|---  
Connection | Create a connection using database token  
Table ID | Enter (or map) your Baserow [Table ID](/user-docs/database-and-table-id) in which you want to create a row. You can find the ID by clicking on the three dots next to the table in the database. It’s the number between brackets.  
Row ID | Enter (or map) the [Row ID](/user-docs/overview-of-rows#what-is-a-row-identifier) whose data you want to get.  
  
![Get a Row](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/684a7f02-be32-47e6-a1b9-3a076e630038/Screenshot_2023-03-17_at_07.23.56.png)

  3. Click “**OK** ” to save this module and “**Run once** ” to test the connection.

### Delete a Row

Deletes an existing row by its ID.

  1. Add the **Delete a Row** module to your Make scenario.

  2. Configure the action

Configuration |   
---|---  
Connection | Create a connection using database token  
Table ID | Enter (or map) your Baserow [Table ID](/user-docs/database-and-table-id) in which you want to create a row. You can find the ID by clicking on the three dots next to the table in the database. It’s the number between brackets.  
Row ID | Enter (or map) the [Row ID](/user-docs/overview-of-rows#what-is-a-row-identifier) whose data you want to delete.  
  3. Click “**OK** ” to save this module and “**Run once** ” to test the connection.

### Update a Row

Updates an existing row by its ID.

  1. Add the **Update a Row** module to your Make scenario.

  2. Configure the action

Configuration |   
---|---  
Connection | Create a connection using database token  
Table ID | Enter (or map) your Baserow [Table ID](/user-docs/database-and-table-id) in which you want to create a row. You can find the ID by clicking on the three dots next to the table in the database. It’s the number between brackets.  
Row ID | Enter (or map) the [Row ID](/user-docs/overview-of-rows#what-is-a-row-identifier) whose data you want to update.  
Row data | Enter (or map) values in the fields. See Baserow’s [guide to permitted field types](/user-docs/baserow-field-overview)  
  3. Click “**OK** ” to save this module and “**Run once** ” to test the connection.

### Make an API Call

Performs an authorized API call.

  1. Add the **Make an API Call** module to your Make scenario.

  2. Configure the action

Configuration |   
---|---  
Connection | Create a connection using database token  
URL | Enter a path relative to `https://api.baserow.io`. For example, `/api/database/fields/table/{table_id}`. For the list of available endpoints, refer to the [database REST API Documentation](/api-docs).  
Method | Select the HTTP method you want to use: `GET` to retrieve information for an entry. `POST` to create a new entry. `PUT` to update/replace an existing entry. `PATCH` to make a partial entry update. `DELETE` to delete an entry.  
Headers | Enter the desired request headers. The authorization headers are added by default.  
Query String | Enter the request query parameters. e.g. `filter__field_1__equal` (key) = `test` (value)  
Body | Enter the body content for your API call.  
  3. Click “**OK** ” to save this module and “**Run once** ” to test the connection.

![Make an API call](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/394d3523-958d-482f-8c7f-72684368d211/Screenshot%202023-03-17%20at%2009.51.19.png)

### List Rows

Finds a page of rows in a given table.

  1. Add the **List Row** module to your Make scenario.

  2. Configure the action

Configuration |   
---|---  
Connection | Create a connection using database token  
Table ID | Enter (or map) your Baserow [Table ID](/user-docs/database-and-table-id) in which you want to create a row. You can find the ID by clicking on the three dots next to the table in the database. It’s the number between brackets.  
Limit | Set the maximum number of rows Make will return during one execution cycle. The default value is 10.  
Search | Enter (or map) a search query to filter rows you want to receive in the output. If no query is provided, all rows within the limit will be returned. If provided only rows with cell data that match the search query are going to be returned.  
  
![Finds a page of rows in a given table.](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/06d14a9e-bbd3-491d-94bd-84ce75989e3c/Screenshot_2023-03-17_at_07.36.38.png)

  3. Click “**OK** ” to save this module and “**Run once** ” to test the connection.

## Related Blog Posts

  * [How to generate content with OpenAI’s GPT-3 and Baserow](/blog/generate-idea-openai-baserow)
  * [How to Build a Custom CMS with Baserow and Webflow](/blog/build-custom-cms-baserow-webflow)
  * [How to Automatically Save Email Attachments to a Database](/blog/save-email-attachments-to-a-database)

