# Baserow Documentation

Source: https://baserow.io/user-docs/n8n

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Configure Baserow in n8n

n8n lets you connect Baserow with hundreds of other apps. Create sophisticated automation between Baserow and your stack.

Create a [Baserow](/) account on any hosted or self-hosted Baserow instance.

## Supported operations

  * **Create -** Create a row
  * **Delete -** Delete a row
  * **Get -** Retrieve a row
  * **Get All -** Retrieve all rows
  * **Update -** Update a row

### Authenticate the [Baserow](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.baserow/) node

n8n credentials are private pieces of information issued by apps and services to authenticate you as a user and allow you to connect and share information between the app or service and the n8n node.

First, add credentials to authenticate the [Baserow](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.baserow/) node,

  1. Open the **Credentials** menu item in n8n and click on **Add credential:**

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/12c6da54-0ce7-49f0-a15e-51e245ba61de/Screenshot_2022-12-05_at_15.53.54.png)

  2. A modal will pop up to select an app or service to connect to. From the dropdown list, choose **Baserow API** and click on the **Continue** button:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/020a3a1f-5e67-42b2-995f-d49dd6650148/c3ce3328e194cb38953ea0192be85d9583e2ce39.webp)

  3. The **Host** is set to `https://api.baserow.io` by default. Leave the default **Host** if you are using the online version of Baserow, otherwise set it to your self-hosted instance API URL.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/17670cb5-7908-4d40-a711-d94b46d5b629/Screenshot_2022-12-05_at_16.05.27.png)

  4. Enter your Baserow login username and password in the respective fields

  5. Click the **Save** button

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/fcb26129-bd5c-4762-84f8-d3f0d435a22a/Screenshot_2022-12-05_at_16.07.22.png)

> For a detailed tutorial, refer to this article on [How to Automate Emails from a No-Code Database with n8n](/blog/automate-emails-from-database-with-n8n).

### Create a row in a table

In your Baserow node, enter your credentials for the Baserow node. The start node is the first node in a workflow and is added by default when you create a new workflow.

  1. Enter your Baserow instance URL (the default value is for the official version).
  2. Select ‘Create’ from the  _**Operation**_ dropdown list.
  3. Enter the Table ID in the  _**Table ID**_ field. To obtain the Table ID, see the Database API page available from the database menu.
  4. Click on  _**Execute Node**_ to run the node.

## Tutorials

  * [Automate Emails from a No-Code Database with n8n](/blog/automate-emails-from-database-with-n8n)
  * [Update Row Data With Baserow Forms](/blog/update-row-data-with-baserow-forms)

