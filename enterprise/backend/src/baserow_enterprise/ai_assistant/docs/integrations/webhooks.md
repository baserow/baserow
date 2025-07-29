# Baserow Documentation

Source: https://baserow.io/user-docs/webhooks

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Configure Webhooks in Baserow

Webhook events provide an efficient way to stay informed about changes in your data, views, and filters. By setting up webhooks, you can receive real-time notifications whenever specific actions are performed in your table, allowing for more streamlined data management and improved workflows.

This section will cover setting up a webhook in Baserow to connect with external applications and automate tasks based on specific events within your Baserow tables.

## Overview

Webhooks can be used to inform 3rd party systems when rows in Baserow have been created, updated, or deleted, and receive real-time notifications about all changes that are made in your table. You can even trigger a test to make sure everything works before saving it.

With batch create/update/delete rows endpoints, you can modify multiple rows at once.

By setting up webhooks, you can receive real-time notifications whenever specific actions are performed in your table, allowing for more streamlined data management and improved workflows.

> If you are using the deprecated webhooks - `row.created`, `row.updated` and `row.deleted` \- It is highly recommended to convert all webhooks to the new types - `rows.created`, `rows.updated` and `rows.deleted`.

## Webhook events

Webhook events notify you whenever a specific action happens in the table, enabling faster response times and more efficient data management.

They provide real-time data to other applications, making it easier to stay updated without needing to constantly check for changes manually. Instead, webhooks push the data to your table as events occur.

Webhooks can be used to monitor the following events:

  * View created, updated, and deleted: Receive notifications when views are added, modified, or removed from your table.
  * Field created, updated, and deleted: Track changes to filters or fields, enabling you to stay up-to-date with data modifications.
  * Conditional row update: Trigger events based on changes to specific field values within a row, providing targeted and relevant updates.
  * Row update: Get notified whenever a row in your database is updated, ensuring you’re aware of all data changes in real-time.
  * Row enters view: Get notifications when a new row is created that matches the view’s filter conditions, or when an existing row is updated to match the filter (if it didn’t match before).

Webhooks will trigger on related row changes by default. To disable these notifications, select **Let me select individual events** and uncheck related rows in the table selection modal.

![Screenshot showing Baserow webhook events](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/c8a89e4d-91cc-4aa5-ac11-8099afa3c003/new_webhook_types.webp)

### Row webhooks

This webhook is triggered every time any row is created, updated, or deleted. It provides a general-purpose event to monitor changes to row data.

  * Rows are created
  * Rows are updated
  * Rows are deleted

### View webhooks

View webhooks allow you to receive notifications whenever views in your table are created, updated, or deleted. A view refers to a specific configuration of data (such as filtered or sorted lists), and knowing when views change can be important for managing workflows, dashboards, or reports.

  * View is created: Triggers when a new view is created.
  * View is updated: Triggers when an existing view is updated.
  * View is deleted: Triggers when a view is removed.

### Field webhooks

These webhooks notify you when fields are created, updated, or deleted. This is important for tracking data structure changes that can affect how data is managed and queried.

  * Field is created: Triggers when a new field is added.
  * Field is updated: Triggers when an existing field is modified.
  * Field is deleted: Triggers when a field is removed.

### Conditional row update

Conditional update provides more granular notifications by only triggering events when a selected field value changes. This makes it possible to receive notifications that are highly relevant and tailored to the most important data changes.

Select specific fields to trigger only when the cell values of the selected fields are updated. For example, you might set up a webhook that sends a message to a user when the “Status” field in a row changes from “Pending” to “Approved”.

## Create a webhook

To set up a new webhook,

  1. Click on the ••• beside the required view or table
  2. Select **Webhooks**
  3. Click ‘Create webhook +’ and Enter a name to identify the webhook by
  4. Before you can receive webhook notifications, you need to define a webhook URL where the notifications will be sent. This URL should point to the endpoint capable of receiving and processing the webhook events. Select the Method and enter a valid webhook URL to send the request to in the required field. Baserow offers `GET`, `POST`, `PUT`, `PATCH`, `DELETE` methods, which include automatic data parsing.
  5. Select which events should trigger the webhook. Choose the option to send everything or specify specific webhook events you want to listen for.
  6. You can send specific headers by filling in the Name and Value fields in the **Headers** section.
  7. Preview the **Example payloads** for events
  8. Ensure that the receiving system can properly handle incoming notifications. This involves validating the request payload and confirming that the events are being processed without errors. Click the **Trigger test webhook** button to test the webhook.
  9. Click **Save**.

Perform test actions within your table to verify that your webhook setup works as expected. For instance, create a new view or update a filter, and check whether the appropriate notifications are being sent to your endpoint.

![Create a webhook in Baserow](https://baserow-media.ams3.digitaloceanspaces.com/pagedown-uploads/c9dbd5a5-d7f0-4a2b-a1f5-fdbf08d04376/Screenshot%202022-08-01%20at%2011.29.49.png)

## Edit webhook

After you create a webhook, you can edit the fields to modify your output.

To edit a new webhook,

  1. Click on the ••• beside the required view or table
  2. Select **Webhooks** and click on **details** to reveal the webhook
  3. Navigate to the ‘Edit’ view
  4. Edit the required fields
  5. Click **Save**.

![Edit webhook in Baserow](https://baserow-media.ams3.digitaloceanspaces.com/pagedown-uploads/2155abed-e5f5-4b86-aaa7-7c1f6e74d3bb/Screenshot%202022-08-10%20at%2021.19.02.png)

You can click on **Delete** at the bottom of the screen to delete the webhook. Note that if you delete a webhook, you will not be able to restore it later.

![enter image description here](https://baserow-media.ams3.digitaloceanspaces.com/pagedown-uploads/613b0e8d-9026-4356-85a7-318ae5838c08/Screenshot%25202022-08-10%2520at%252021.15.45.png)

Click the **Trigger test webhook** button to validate all entries.

## Webhook payload structure

When a webhook event is triggered, a payload is sent to your designated URL. Below is a sample structure of a webhook payload:

Example webhook payload for “View Created”:
    
    
    {
        "table_id": 50000,
        "database_id": 1000,
        "workspace_id": 300,
        "event_id": "00000000-0000-0000-0000-000000000000",
        "event_type": "view.created",
        "view": {
            "id": 0,
            "table_id": 0,
            "name": "View",
            "order": 1,
            "type": "grid",
            "table": null,
            "filter_type": "AND",
            "filters_disabled": false,
            "public_view_has_password": false,
            "show_logo": true,
            "ownership_type": "collaborative",
            "owned_by_id": null,
            "row_identifier_type": "id",
            "public": false
        }
    }
    

In this payload:

  * `table_id`, `database_id`, and `workspace_id` refer to the specific table, database, and workspace in which the view is created.
  * `event_type` specifies the type of event (e.g., view.created).
  * The `view` object contains details of the newly created view, such as its name, order, type, filter settings, and ownership.

## View webhook call log

For each webhook, you can view the response and request. This can be useful if a call fails and you need to access why.

To view a log of the calls for a webhook,

  1. Click on the ••• beside the required view or table
  2. Select **Webhooks and click on “details”** to reveal the webhook
  3. Navigate to the ‘Call log’ view

![View webhook call log in Baserow](https://baserow-media.ams3.digitaloceanspaces.com/pagedown-uploads/cb9cb4e0-b41a-4160-9dd9-3245612c75ab/Screenshot%202022-08-10%20at%2021.26.20.png)

Within the call log page, you can view each call event, URL, time, request, and response.

## Error handling & retries

In case the webhook endpoint is temporarily unavailable or returns an error, Baserow will attempt retries a limited number of times. Make sure your webhook endpoint is reliable and can handle spikes in traffic. It’s also essential to return a `200 OK` status code upon successfully receiving the webhook to avoid unnecessary retries.

