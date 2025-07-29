# Baserow Documentation

Source: https://baserow.io/user-docs/activate-enterprise-license

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Activate Enterprise License

This section will walk you through activating the [Enterprise version](/user-docs/enterprise-license-overview) on your self-hosted Baserow server for Baserow versions 1.14.0 and greater.

## Steps to Activate Enterprise

### 1\. Contact Sales

Upgrading to the Enterprise plan is a manual process handled by the Baserow sales team. Please first [contact a sales representative](/contact-sales) to get started with the Enterprise plan.

### 2\. Setup or Upgrade a Baserow Server

Baserow’s Enterprise version is only available for self-hosted Baserow servers **on Baserow version 1.14.0 or greater**. It is not available for workspaces on [Baserow.io](http://Baserow.io) itself.

  * See our [installation documentation](/docs/installation%2Finstall-with-docker) for options for setting up a self-hosted Baserow server if you don’t already have one.
  * If you already have a Baserow server ensure it is already upgraded and running on **Baserow version 1.14.0 or greater**. You can verify you are on 1.14.0 by expanding the Admin section in the sidebar of Baserow and verifying you can see a greyed-out or active “Audit Log” button.

### 3\. Find your Instance ID

For the Baserow server that you want to activate enterprise on, you will need to provide your sales representative with the server’s Instance ID. To find your Instance ID:

  1. Log in to your Baserow server as an Instance Admin. Instance Admins have staff access to the entire self-hosted instance. The first user who signed up is automatically an Instance Admin.
  2. Expand the Admin section at the top of the left sidebar.
  3. Open the Licenses page in the Admin section.
  4. Copy your Baserow servers Instance ID.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/efd0ac6e-04ef-4235-b85b-bdf3a89f5aba/Untitled.png)

### 4\. Install your Enterprise license key

Next, you should send the server’s instance ID to your sales representative, who will then send you back an Enterprise License key. Once you have your Enterprise License key, you can install it into your server by:

  1. Go to the Licenses admin page where you got your Instance ID above.

  2. If you have any old expired licenses, click on each one and select **Disconnect License** and remove them permanently.

If you had previously activated your enterprise license in 1.12.X or earlier it will be showing up as expired after upgrading to 1.14.0. You must also disconnect and re-register this license.

  3. On the Licenses admin page click **Register License** and enter your new Enterprise license key.

  4. Your Enterprise license will immediately become active for every single user of your Baserow server. There is no need to assign individual seats to users as the Enterprise license is global.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/a06a7ac8-5a32-47f9-9d31-af855948b3fa/Untitled%201.png)

## Updating an Existing License

If you have already registered a Baserow Enterprise or Premium license in your self-hosted server, Baserow will automatically attempt to fetch any changes to your license every hour if it can access the internet.

> If an enterprise license was activated in Baserow versions 1.12.X or older it will show as expired after upgrading to 1.14.0. You should disconnect the license and re-install it after upgrading to fix this issue.

Changes to licenses are made by the Baserow sales team. For example, these changes could be:

  * An upgrade of the type of your existing license from Premium to Enterprise, or
  * An updated expiry date.

You can also manually trigger this update by clicking the **Check Now** button on your Licenses detail page.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/688840c3-36d6-4e98-83a3-ec909cdb204b/Untitled%202.png)

### Update a license on a server without internet

This section will cover how to update a license on a server that can’t reach the internet.

If your Baserow server is on an air-gapped network or behind a firewall that prevents it from requesting updated license details every hour, then automatic changes made by the Baserow sales team to your license will not be picked up.

To get updates you should:

  1. Inform the Baserow sales team that your Baserow server cannot access the internet and so you need to get manual license updates.

  2. When the Baserow sales team, as discussed with you, makes any changes to your license they will send you a new license key.

  3. You should take this new license key and register it in your Baserow server following the steps in the **Install your Enterprise license key** section above.

  4. Once your new updated license has been entered, click on your old License on the Licenses Admin page and click the “Disconnect License” to remove the old version.

> After disconnecting an old enterprise license you might see your feature badge in the top left of Baserow change to become `Premium`. This is a known bug in 1.14.0 and simply refreshing the page will re-enable your enterprise features for your user.

## Troubleshooting

### How can I tell if Enterprise is active?

Look for the `Enterprise` badge in the top left corner of Baserow. If the badge is present, then your Enterprise plan is active.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/85c603bf-aa65-4a83-9272-fee8cc33169a/Untitled%203.png)

### How do I check if I am using the right version of Baserow?

Open the Admin menu in the sidebar and check to see if you can see the **Audit Log** button. If it is present (even if greyed out) you are on 1.14.0 or greater and can activate the enterprise license. If you cannot see the **Audit Log** admin page then you first must upgrade your Baserow version to 1.14.0 or greater to use Enterprise.

Refer to our documentation for a guide on how to [upgrade from a previous version](/docs/installation%2Finstall-with-docker#upgrading-from-a-previous-version).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/25b614b6-9caa-4a74-806d-53efe203b8d6/Untitled%204.png)

### How can I allocate users’ seats?

The enterprise license grants every current and future user on your instance the enterprise features. You do not need to allocate seats to individual users on the Enterprise license as they will automatically get the features.

### I don’t have the enterprise features after registering the license

Make sure you are using Baserow 1.14.0, older versions will not work with the enterprise version. Refer to our documentation for a guide on how to [upgrade from a previous version](/docs/installation%2Finstall-with-docker#upgrading-from-a-previous-version).

Otherwise, try logging out of Baserow and back in again.

### I upgraded to 1.14.0 and my enterprise license now shows as expired

If an enterprise license was activated in Baserow version 1.12.X or prior, it will show as expired after upgrading to 1.14.0. To resolve this issue, disconnect and reinstall the licence after upgrading to 1.14.0.

