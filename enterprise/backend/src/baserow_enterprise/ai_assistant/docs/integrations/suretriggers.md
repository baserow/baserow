# Baserow Documentation

Source: https://baserow.io/user-docs/suretriggers-integration

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Configure Baserow in SureTriggers

SureTriggers offers the ability to create custom workflows that perform actions in response to specific triggers. You can seamlessly sync data from Baserow to over 600 apps using various triggers.

With SureTriggers, you can connect Baserow to multiple apps and services, automating repetitive tasks without coding and creating custom automation that executes specific actions based on particular events.

This guide will walk you through configuring Baserow to function as a trigger app and initiating actions in another application based on events within Baserow.

![Suretriggers with Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/74efa791-456d-47a0-bc4b-625af008da93/SureTriggers.jpg)

## Prerequisites

  * An existing [Baserow](/) account and workspace.
  * A [SureTriggers](https://suretriggers.com/integrations/baserow/) account with access to create workflows.
  * Familiarity with Baserow functionalities (tables, fields, rows).

## Supported operations

  * Row Created - Runs when a new row is created.
  * Row Updated - Runs when a row is updated.
  * Row Deleted - Runs when a row is deleted.

> Alternatively, use the Webhook app to trigger when the Webhook receives data.

## Configure Baserow in SureTriggers

Create a workflow in SureTriggers. A trigger is an event that starts your workflow to streamline your processes and enhance productivity.

### Choose Baserow as the trigger app

Browse the available apps and choose Baserow as the trigger app. A trigger app initiates a workflow based on specific events happening within the app. In this case, Baserow will be the starting point for your automated processes.

Choose the specific event in Baserow that will initiate your workflow. Actions within Baserow, such as adding a new row, or updating or deleting an existing row, will prompt a response in another application.

![Set up Baserow trigger in SureTriggers](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2cec5e44-98c9-4358-84ce-a253a4f42879/suretriggers%20set%20trigger.png)

### Add the Webhook URL to Baserow

You’ll need to provide Baserow with the webhook URL it should use to send notifications to other applications.

> For more information on creating a webhook in Baserow, see the [support documentation](/user-docs/webhooks).

On the side menu bar, navigate to the database containing the table or view where you want to set up the webhook. Locate the three dots icon in the top bar of a table in Baserow. Select **Webhooks** from the dropdown menu and create a webhook.

  1. Select **POST** from the **Method** dropdown menu (this is the most common method for webhooks)

  2. Copy the URL from SureTriggers and paste it into the **URL** field within Baserow.

> A typo or error in the URL will prevent Baserow from successfully communicating with other applications. Double-check the URL for any mistakes before saving the webhook configuration.

  3. Choose the specific events that should trigger the webhook. For instance, if you want the webhook to activate when a new row is added, select the “Rows are created” checkbox.

  4. You can test the webhook functionality by clicking the **Trigger test webhook** button in Baserow. This will send a test message to the defined URL and display the response within Baserow.

![Baserow Webhook suretriggers](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d2d504cf-47cc-4cd9-8e99-faa469ee235c/iNCOMING%20webhook.png)

### Save and test the workflow

After selecting the trigger, SureTriggers will guide you through defining the actions that follow the trigger event. These actions can involve sending data to another application, calculating, or creating notifications.

Once you’ve configured the trigger and subsequent actions, save your workflow and run a test to ensure everything functions as expected. Baserow should initiate the workflow based on the chosen trigger event.

![test Baserow webhook in suretriggers](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/fa28096e-3f32-4ec2-856e-e2dcb007ae0a/test%20webhook%20suretriggers.png)

By following these steps, Baserow will be equipped to send notifications to the other applications whenever the designated events occur within your Baserow tables.

## Related content

  * [Make integration](/user-docs/make)
  * [Zapier integration](/user-docs/zapier)
  * [Baserow webhooks](/user-docs/webhooks)
  * [Backend API](/docs/apis%2Frest-api)

