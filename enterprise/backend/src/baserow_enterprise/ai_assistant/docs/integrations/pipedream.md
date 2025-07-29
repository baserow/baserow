# Baserow Documentation

Source: https://baserow.io/user-docs/pipedream

---


## Supported operations

  * Use any Baserow API in Node.js
  * Use any Baserow API in Python

## Create a new workflow

Every Pipedream workflow begins with a single  _trigger_ step. _Triggers_ define the type of event that runs your workflow. Log in to Pipedream then click on the New+ button to create a [new workflow](https://pipedream.com/new):

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/77d369a4-47a1-42fa-a1ed-d783b89859f8/Screenshot_2022-10-18_at_15.30.21.png)

## Add a trigger

Select a trigger in the workflow builder. For example, select the **HTTP / Webhook Requests** trigger to listen to incoming events on this workflow:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/fe0aeb19-f37b-413e-b706-16f16bfa5e0c/Screenshot_2022-10-18_at_15.42.25.png)

Select **HTTP Requests** to get a unique URL where you can send requests to trigger your workflow. Customize the Event Data, HTTP response and filters:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/c9715466-ab59-4a94-9d24-509c525425c9/Screenshot_2022-10-18_at_15.46.05.png)

Pipedream will generate a unique URL where you can send HTTP requests to trigger this workflow:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/444b9430-964c-4816-b5ed-34a5f5bc4e3d/Screenshot_2022-10-18_at_15.49.01.png)

## **Send data to the workflow**

Visit [Baserow](/) to create an account. To get started, read our documentation on [how to create a database](/user-docs/create-a-database).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/6abc5ca1-ff1c-49fe-8d34-dd959dbe7fe8/Untitled.png)

[Create a table](/user-docs/create-a-table) to collect information, like name, description, email, etc. These fields will help us configure the Baserow step of the workflow.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2e858f31-deb6-4f4d-ac84-341a3bcea2b5/Screenshot_2022-10-18_at_16.10.27.png)

Next, send data to the trigger URL to help you build the workflow. Enter the webhook URL on Baserow to send the request to in the required field. Webhooks can be used in order to inform 3rd party systems when rows in Baserow have been created, updated or deleted.

> To learn more about setting webhooks, read our documentation on [creating and editing webhooks](/user-docs/webhooks).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/20ca3d93-9a06-4da0-99c8-22220809ff0b/Screenshot_2022-10-18_at_15.58.39.png)

When Pipedream receives the request, it will be available to select from the event selector. Click on the drop-down menu and select the event generated:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/991d6729-1e1e-4614-87bc-cb11927c5647/Screenshot_2022-10-18_at_15.59.59.png)

Pipedream will automatically display the contents of the selected event. The trigger has an event that contains a body with customer data. Expand the `body` to validate that the message was received:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/296ed7a0-43ef-42c5-8ab4-d8859f079e8d/Screenshot_2022-10-20_at_05.47.16.png)

As you construct your workflow, autocomplete suggestions will be based on the selected event. The information will also be used to test further steps.

## Save data to Baserow database

Next, let’s add a step to the Pipedream workflow to send the data to another Baserow database.

Click **Continue** or the **+** button to add a new step to this workflow. That will open the **Add a step** menu. Select **Baserow** app:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/08542848-9dc2-404d-af9d-0430f6e59dd3/Screenshot_2022-10-18_at_16.14.28.png)

Select the **Use any Baserow API in Node.js** action to connect your account and customize a Baserow API request:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/f4e3aa07-b014-4721-8c04-6a23d202f549/Screenshot_2022-10-18_at_16.16.01.png)

You can also **Use any Baserow API in Python** to customize a Baserow API request.

Connect your Baserow account to Pipedream (or select it from the dropdown if you previously connected an account):

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/955c611f-9e79-48fc-93ca-414e426b6c3d/Screenshot_2022-10-18_at_16.20.46.png)

Baserow uses a simple token based authentication. You need to generate at least one API token in your settings. When you connect your Baserow account, Pipedream securely stores the keys so you can easily authenticate to Baserow APIs in both code and no-code steps.

Visit your [account settings](/), copy your API token, and enter your Baserow token on Pipedream.

> To generate a database token, read our [documentation on API tokens](/user-docs/personal-api-tokens).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/43c158f1-3fe1-4db0-a735-198157364c5b/Screenshot_2022-10-18_at_16.34.40.png)

Return to Pipedream and your connected account should automatically be selected.

### Add a custom code step to the workflow

Pipedream Code steps drive the logic of your workflow and let you write any custom Node.js code. The workflow builder will accept text input to populate the steps.

To use webhook data from prior trigger step in the code step, pass props to code steps as arguments or parameters entered in the workflow builder.

Define individual `props` in a Node.js code step to make code steps reusable. The keys of the objects are the names of the props. For example:
    
    
    props: {
        msg: {
          type: "string",
          label: "Message",
          description: "Enter a message to `console.log()`",
        },
      },
    

To generate the fields from the pre-built trigger step, click on **Refresh fields** button to read the props and generate the fields from prior steps:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/56e30e1f-6c8f-497a-a131-b1fc0d855f2e/Screenshot_2022-10-20_at_06.20.22.png)

Use the object explorer to pass the data for the workflow event as the values. This data can be found in the context object on the trigger.

When you click into a field, Pipedream will display an object explorer to make it easy to find data. Scroll or search to find the key under `steps.trigger.event.body.items` and click **select path** to connect them to the Baserow step. That will insert the reference:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/7e17c1ad-3e60-4b4b-b7c5-fadcfcc93529/Screenshot_2022-10-20_at_06.23.55.png)

Next, replace the `[Table_ID]` :

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/1da2aca0-207b-4174-a01f-2f21663ef8db/Screenshot_2022-10-18_at_16.45.17.png)

Return the configured value of the prop with `this.myPropName`:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/492da8b5-7298-4aaa-ad84-a5d8ee0642d9/Screenshot_2022-10-20_at_06.33.33.png)

After the configuration is complete, click **Test** to validate the configuration for this step. When the test is complete, you will see a success message and a summary of the action performed:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9abbd422-7e4f-413e-a75f-6b07f9d1316d/Screenshot_2022-10-18_at_16.49.37.png)

Customize the name of your workflow. Then click **Deploy** to run your workflow on every trigger event.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d6521859-d239-447e-ac82-d93c2b52f415/Screenshot_2022-10-18_at_17.06.48.png)

Anytime the workflow runs, Pipedream will execute each step of your workflow in order.

You can view the webhook response and request on Baserow. This can be useful if a call fails and you need to access why.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/352662e8-3a2b-4aa3-8fc2-70c15a0ff89a/Screenshot_2022-10-20_at_06.40.06.png)

