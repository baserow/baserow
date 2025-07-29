# Baserow Documentation

Source: https://baserow.io/user-docs/element-events

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Element events

Element events let you decide what happens when someone clicks on things like buttons. This makes the user experience lively and responsive.

Here, we’ll look at how to make buttons interactive in an application. By connecting button clicks to certain actions, you make the user experience better and guide the way the application works.

![Events](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b31f7848-089d-44d8-a300-404d6d7bab80/Untitled.png)

## Overview

Events are triggers within your application that respond to user interactions, like [clicking a button](/user-docs/application-builder-button-element), [logging in](/user-docs/application-builder-login-element), or [submitting a form](/user-docs/application-builder-form-element). They bridge the gap between user input and actions on the application’s data.

You can create an action on click or after login.

Here’s an overview of the actions:

  * **Show notification** : This action triggers a notification to alert users about updates, messages, or system events within the application.
  * **Open page** : This action opens an external URL.
  * **Logout** : This action logs a user out of the application.
  * **Refresh data source** : This triggers the data sources on the page to be refreshed to account for recent changes.
  * **Send HTTP request** : Allows you to send requests to external APIs and services.
  * **Send email** : Sends a customized email to specified recipients directly from the application, enabling automated communication using any SMTP server of your choice.
  * **Create row** : This action creates a new row in the selected table. Choose a table to begin configuring fields.
  * **Update row** : This action updates an existing row in the selected table. Choose a table to begin configuring fields.
  * **Delete a row** : This action deletes an existing row in the selected table. Choose a table to begin configuring fields.

You can reorganize the events using the drag-and-drop handle.

## Element action: Show notification

Notifications are key for user feedback in your application.

The “Show notification” feature in Application Builder lets you make short messages that pop up on the screen. They tell users about what’s happening in your application and then disappear quickly. This way, users get updates without any mess on the screen.

For example, when someone sends a form, they can’t see what happens next. They might wonder if it worked. That’s where “Show notification” comes in. It gives them a clear message like “Form submitted successfully!” or “Thank you for your inquiry!” to let them know everything was successful.

![Show notification](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/3c68c1dc-31f2-47f9-9723-bf06abe761d5/Untitled%201.png)

## Element action: Open a page

When a user clicks the button, it directs them to another page.

This feature is perfect for when you want users to go to a certain page after logging in or on click. It could be a confirmation page, a thank you page, or a page with more information.

This improves user flow by directing users to a specific web address. It’s handy for accessing related links.

## Element action: HTTP request

The HTTP request action allows you to send requests to external APIs and services directly from your application. This powerful feature enables integration with third-party systems, data submission to external endpoints, and triggering of external workflows.

Here’s how it works:

  1. **Choose HTTP method** : Select the appropriate HTTP method (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS) for your request.
  2. **Configure the endpoint url** : Specify the URL of the API endpoint you want to send the request to.
  3. **Set query parameters** : Add any necessary query parameters.
  4. **Set headers** : Add any necessary headers for authentication, content type, or other requirements.
  5. **Select body type** : Body content can be sent as JSON, form multipart and raw.
  6. **Include request body content** : Set the body content, you can include data from form fields or other available data sources.
  7. **Timeout** : Set the amount of time this request has to succeed before timing out and failing.

This action is perfect for integrating with payment processors, sending data to CRM systems, triggering automated workflows, or communicating with any external API that your application needs to interact with.

## Element action: Create a row

This event lets users submit data that [creates a new row in a table](/user-docs/how-to-make-new-rows). It’s perfect for building forms to collect data, like applications, feedback, or purchase orders.

Here’s how it works:

  1. **Choose a database** : Select the database containing the table where you want to create new rows.
  2. **Specify the target table** : Pick the specific table within the chosen database that will receive the new rows.
  3. **Map form fields** : Match the fields in the form with the corresponding fields in the table. This ensures the data gets placed in the correct location within each row.

For example: A job application form creates a new record in a “Job Applications” table with the applicant’s details and the specific job they’re applying for. Whenever an applicant submits the form, a new row will be created in the table, automatically capturing their information.

![Create a row event in Baserow Application Builder](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/743f7e55-467f-4acf-b276-12bbeaab4df4/Untitled%202.png)

## Element event: Update an existing row

This event allows users to modify existing data entries within the application. It facilitates the editing process, allowing users to make necessary changes to the data.

For example, if you have a list of tasks, the task page can contain a form through which employees can request task changes.

  1. **Configure the update action:** In the Events tab of the Application Builder, select the [integration](/user-docs/application-settings), [database](/user-docs/intro-to-databases), [table](/user-docs/intro-to-tables), and specific [row](/user-docs/overview-of-rows) you want to update after the event occurs.
  2. **Define updatable fields:** Choose which data fields from the application users can modify through the form.

After the event occurs, the application automatically updates the designated row with the new information, reflecting the user’s requested changes.

![Update row event in Baserow Application Builder](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b07285b6-777b-44b2-86ad-4bbb4acfb0f5/Untitled%203.png)

## Element event: Send an email with SMTP

You can send custom emails using the **Send email** action inside your workflow. All you need is access to an SMTP server like Gmail, Outlook, or your company mail.

* * *

### Step 1: Add a “Send email” action

  1. Navigate to the **Events** tab.
  2. Select an event trigger, such as **On click**.
  3. Click the **+Add action** button and choose **Send Email** from the list.

### Step 2: Configure your SMTP integration within the action

You will be prompted to set up an SMTP integration to send emails.

Field | Description  
---|---  
SMTP Host | The SMTP server address, e.g., `smtp.gmail.com`  
SMTP Port | Typically `587` for TLS or `465` for SSL  
Use TLS | Enable if required (✅ recommended for Gmail, Outlook, etc.)  
Username | Your full email address  
Password | Your email password or an app-specific password (recommended)  
  
> 💡 **Note for Gmail users:** You need to create an App Password and use it here instead of your regular email password.

Once saved, this SMTP integration will be available for all future email actions.

### Step 3: Compose your email

Fill in the email details to customize your message:

Field | Description  
---|---  
To | Recipient’s email address  
Subject | The subject line of your email  
Message | Email body content (supports both plain text and HTML)  
  
You can also configure additional fields such as _CC_ , _BCC_ , and select the _Body Type_ as needed.

Automate confirmations, alerts, and updates based on user interactions.

![Send email event action](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/820cea6d-8d59-485c-bbe4-db29bf3231a7/Send%20email.png)

### Step 4: Add dynamic content (Optional)

Make your emails personal by including data from your forms or database:

  1. Click in any email field (To, Subject, or Message)
  2. Use the data source picker to insert dynamic values
  3. Examples: 
     * **To field** : Use form email input or user’s email from database
     * **Subject** : “Thank you {{form_data.name}} for your submission”
     * **Message** : Include order details, user information, or form responses

This ensures each email is customized for the recipient.

