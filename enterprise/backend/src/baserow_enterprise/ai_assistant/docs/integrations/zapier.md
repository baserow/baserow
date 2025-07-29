# Baserow Documentation

Source: https://baserow.io/user-docs/zapier

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Configure Baserow in Zapier

Zapier connects Baserow to all the software you rely on.

With Zapier, you can build custom workflows that can execute actions in response to a trigger. You can easily connect Baserow to 5000+ apps and services, and automate repetitive tasks without writing code.

Here’s how to get started with [syncing your Baserow database](https://zapier.com/apps/baserow/integrations) to other apps you use.

## Supported Operations

**Triggers** :

  * **Row Created -** Trigger when a new row is created.
  * **Row Created or Updated -** Trigger when a new row is created or an existing one is updated.
  * **Row Updated -** Trigger when an existing row is updated.

**Actions** :

  * **Delete Row -** Deletes an existing row.
  * **Create Row -** Creates a new row.
  * **Update Row -** Updates an existing row.
  * **Get Single Row -** Finds a single row in a given table.
  * **List Rows -** Finds a page of rows in a given table.

## Connect Baserow to Zapier

Create a Zapier account if you don’t already have one. Search for Baserow in the list of available apps and use your credentials to connect your Baserow account to Zapier.

## Create a trigger

A **Zap** is an automated workflow that connects your apps and services together. Zaps help you save time and prevent mistakes by automating some aspects of employee onboarding. Each **Zap** consists of a trigger and one or more actions. A trigger is what starts the Zap. When you start automating your operations, it’s easy to see how Zaps might free you from manual tasks.

First, set up a **trigger** containing the data you want to add.

### Choose app & trigger event

Create a Zap trigger for when a new event occurs in your Baserow table.

Select  _**Baserow**_ as the app, then select the event you wish to occur from the list of possible [Zapier triggers](https://zapier.com/apps/baserow/integrations):

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9fe28816-9aa7-4236-ae51-4eaccdd1949c/Untitled.png)

### Choose Baserow account

If you already have your Baserow account connected to Zapier, select it from the account menu.

If not, click **Create a new account** and follow the instructions to connect your app to Zapier with an API token. An API token is similar to a password and allows Zapier to authenticate to Baserow to perform specific actions.

### Authenticate the Baserow API on Zapier,

  1. Click on the ‘**API Tokens’** tab within your Baserow ‘**Settings’** page to create a Baserow API token
  2. Click on the ‘**Create token +’** button
  3. Input the name and select an existing workspace
  4. Click on the ‘**Create token’** button to create a new API token for the selected workspace and the authorized user.
  5. Input your Baserow API token in the  _Baserow API token_ field on Zapier. Then, click **Continue to** grant Zapier access to your Baserow database.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/fbed3d65-7fb6-4be3-8466-3290b8c361c4/Untitled%201.png)

> For more information about Baserow API token, read our user documentation on [connecting Baserow with other software](/user-docs/database-api).

### Set up trigger

Then select the table you wish to connect to Zapier. Find your [Baserow table ID](/user-docs/database-and-table-id) by clicking on the three dots next to the table. It’s the number between brackets:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/6df72d5d-bc43-4a6f-b09c-b1828a8876cb/Untitled%202.png)

You can choose a response to **test the trigger**. Your test form data will look like this:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/1d625300-3413-412d-abd1-2c38c5e13fba/Screenshot_2022-10-18_at_09.43.20.png)

## Choose an action

An action is an event a Zap performs after it’s triggered, like adding a new record to a Baserow database, notifying your team in Slack or sending a follow-up email.

Select Baserow as the action app you wish to use, then select an action:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/6a706ce7-cda0-4d53-ae5e-0abd9cf1e131/Screenshot_2022-10-18_at_09.56.57.png)

Connect your account to the action app you wish to connect with. Select it from the account menu if you already have an account linked to Zapier.

If not, click **Create a new account** and follow the on-screen steps to link your app to Zapier.

### Set up action

Next, **customize the data** that you want to send over to your action app.

You’ll see dropdown menus and/or form fields to fill out in this step. In this example, we will map the form submission data that we want to sync across database tables.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/5cb49c87-0ba9-4cac-9e9f-fb0824ef7571/Screenshot_2022-10-18_at_10.03.01.png)

> For more information on how to get your row ID, read our user documentation on [row identifiers](/user-docs/navigating-row-configurations#what-is-a-row-identifier-and-count).

### Test the action

The last step is to test whether your action works as expected. The first screen displays the data input for your action—the information sent to your action app. Click **Test & Continue** to start the action step.

The next screen will show you whether Zapier was successful in performing the action step for you.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/4d3d9760-82a3-4924-a711-154629ee50a3/Screenshot_2022-10-18_at_10.10.42.png)

Finally, click on **Publish Zap** button. Once you turn on a Zap, Zapier will monitor for that trigger event.

When the Zap runs, it will execute all actions simultaneously. You can always add extra steps to any Zap to complete the onboarding process in a single Zap.

Get started with [Baserow workflows on Zapier](https://zapier.com/apps/baserow/integrations) to save time.

## Related Blog Posts

For detailed tutorials, refer to these articles

  * [Automate your workflow: Sync Google Sheets and Baserow with Zapier](/blog/google-sheets-baserow-zapier)
  * [Streamline collaboration and review process with database automation](/blog/automate-collaboration-and-review-process)
  * [Automate Custom Notifications from Baserow Form Submissions with Zapier](/blog/how-to-automate-custom-notifications-from-baserow)
  * [Manage User Access to Softr in Baserow Database](/blog/manage-user-access-to-softr-baserow)

