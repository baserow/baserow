# Baserow Documentation

Source: https://baserow.io/user-docs/configure-sso-with-azure-ad

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Configure SSO with Azure AD

This guide is intended for [Admins](/user-docs/working-with-collaborators#set-the-permission-level-for-collaborators) setting up SSO SAML with Azure AD.

When you configure Single Sign-on (SSO) with Azure AD, your users will be able to create and sign into their Baserow accounts using Azure AD.

If you are looking for information on setting up SSO with other providers:

  * [Configure OneLogin for SAML SSO](/user-docs/configure-sso-with-onelogin)
  * [Configure Okta for SAML SSO](/user-docs/configure-sso-with-okta)
  * [Configure Facebook for OAuth 2 SSO](/user-docs/configure-facebook-for-oauth-2-sso)
  * [Configure GitHub for OAuth 2 SSO](/user-docs/configure-github-for-oauth-2-sso)
  * [Configure GitLab for OAuth 2 SSO](/user-docs/configure-gitlab-for-oauth-2-sso)
  * [Configure Google for OAuth 2 SSO](/user-docs/configure-google-for-oauth-2-sso)
  * [Configure OpenID Connect for OAuth 2 SSO](/user-docs/configure-openid-connect-for-oauth-2-sso)

> Instance-wide admin panel, SSO, Payment by invoice, Signup rules, and Audit logs are features only available for Baserow paid plans. [Get in touch with us here](/contact-sales) if you’re interested in learning more about paid pricing.

Here’s how to set up Azure AD to sign in to your Baserow account.

## Prerequisites

To set up SSO SAML with Azure AD in Baserow, you need:

  * A Baserow user account. If you don’t already have one, you can create an account.
  * Instance admin access to the entire Baserow self-hosted instance.
  * An Azure AD user account with Global Administrator, Cloud Application Administrator, or Application Administrator role.

## Create an Azure application and set up SAML SSO

  1. To add an enterprise application to your Azure AD tenant, sign in to the [Azure Active Directory Admin Center](https://aad.portal.azure.com/).

  2. In the Azure portal, select **Azure Active Directory > Enterprise applications** and select **New application**. Then click **+** **Create your own application**.

  3. Enter the display name for your new application, select **Integrate any other application you don’t find in the gallery** , and then select **Create** to add the application.

![Create an Azure application and set up SAML SSO](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/14d7d65d-72c2-4887-9c07-41d6773a3836/Untitled.png)

  4. In the left menu of the app’s **Overview** page, select Single sign-on.

  5. Select **SAML** as the single sign-on method.

![Select SAML as the single sign-on method.](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/56dcc35d-684b-4ff7-8c53-bda9b5f7ba3e/Untitled%201.png)

  6. The **Set Up Single Sign-On with SAML** page will then open.

## Get your Baserow SSO URLs

  1. In a new tab, visit your Baserow server and log in as an instance-wide admin.
  2. Open the **Admin** section in the Baserow sidebar.
  3. Click the **Authentication** page.
  4. Click the **Add Provider** button in the top right.
  5. Select SSO SAML provider.
  6. In the **Add a new SSO SAML provider** modal that has opened, copy the **Single Sign on URL.**

![Add a new SSO SAML provider](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/baf9a014-18f4-41d8-bb84-2717111897a8/Screenshot_2023-02-15_at_09.24.55.png)

## Configure SAML URLs in Azure

  1. Go back to Azure and the **Set Up Single Sign-On with SAML** page.

  2. In the first section titled Basic SAML Configuration, click the **Edit** button.

  3. Paste the **Single Sign on URL** you copied from **Baserow into the top three fields:**

     1. Identifier (Entity ID)
     2. Reply URL (Assertion Consumer Service URL)
     3. Sign on URL
  4. Go back to Baserow and the previously opened **Add a new SSO SAML provider** modal and now copy the **Default Relay State URL.**

  5. Go back to Azure and paste the **Default Relay State URL** from Baserow into the Relay State field in Azure.

  6. Leave the Logout URL empty as Baserow does not yet support single sign out.

  7. Finally, click **Save** in Azure, your end result should look something like the following screenshot:

![Configure SAML URLs in Azure](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/5813c58e-be81-46c2-aff4-f0bc46a607e6/Untitled%202.png)

## Setup Azure Attributes & Claims

  1. Go to the second section in Azure titled Attributes & Claims, then click the **Edit** button

  2. On the new Attributes & Claims page click **Add New Claim**.

     1. Type ‘user.email’ in the Name field

     2. In the Source attribute dropdown, select **user.mail**

     3. Click **Save**

![Setup Azure Attributes & Claims](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/0096eb01-2d16-46d7-bd06-4f18b222b2ee/Untitled%203.png)

  3. Click Add New Claim again

     1. Type ‘user.first_name’ in the Name field

     2. Select **user.givenname** from the Source attribute dropdown.

     3. Click **Save**

![Add New Claim again](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/ec4f0e04-78fa-4951-b726-c578b2cee2db/Untitled%204.png)

  4. The end result of your Attributes & Claims page in Azure should now look something like this:

![Attributes & Claims page in Azure](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/04021e51-ed84-45f8-8ef8-cae4c087f963/Untitled%205.png)

  5. Click the **X close** button in the top right of the Attributes & Claims page in Azure to get back to the **Set Up Single Sign-On with SAML** page.

## Fix and install Azure SAML metadata in Baserow

  1. Next in the third section titled SAML Certificates next to Federation Metadata XML click **Download**.

![Fix and install Azure SAML metadata in Baserow
](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b02c2d10-777b-4910-a78d-9284b0ea393d/Screenshot_2023-02-15_at_09.56.47.png)

  2. Open the download XML file in a text editor.

     1. By default, Microsoft includes both SAML 2.0 and Web Services Federation configuration in this XML file. Baserow only supports SAML 2.0 and so you will now need to delete the redundant Web Services Federation configuration from this file, if you do not Baserow will not accept the metadata.
     2. To fix this open up the downloaded XML metadata file in a text editor.
     3. Edit the file by deleting the text starting from and including `<RoleDescriptor` all the way up to and including the **very last** `</RoleDescriptor>` in the metadata file. 
        1. For example, given the following example metadata file
               
               <ExampleMetaDataHere><SomeOtherData/><RoleDescriptor...>..</RoleDescriptor><RoleDescriptor...>.</RoleDescriptor></ExampleMetaDataHere>
               

        2. The end result should look like the below, without any RoleDescriptor sections.
               
               <ExampleMetaDataHere><SomeOtherData/></ExampleMetaDataHere>
               

        3. If you are having trouble with this step please ask for help by asking your Baserow sales rep.

     4. Copy the resulting metadata which has had the RoleDescriptor sections removed.
  3. Go back to Baserow and the previously opened **Add a new SSO SAML provider** modal. Paste the contents of the edited file you just copied into the **metadata** box and click **Save**.

![Go back to Baserow and the previously opened](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/96130543-fccb-49d2-ab10-ed5daf41beaa/Untitled%206.png)

  4. Go back to Azure and in the left sidebar click **User and workspaces**.

  5. Click **Add user/workspace** and on the **Add Assignment** page that opens select all users and workspaces you wish to be able to login to your Baserow server, then click **Assign**.

## Testing SSO In Baserow

You should be able to log in with Azure AD after completing these steps by visiting your Baserow servers login page. Your users will now be taken to an Azure AD sign-in flow when they attempt to log into Baserow. After logging in with their Azure AD credentials, they will be redirected to the app.

![Testing SSO In Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/be33533b-090f-40a3-a9b0-19c7be3b187b/Screenshot_2022-11-04_at_07.02.25.png)

## Understanding Baserow’s authentication system

By default, Baserow restricts users to logging in only with the same authentication method they used for signing up. For instance, if a user creates an account with a username and password, they won’t be able to log in through SSO without further configuration.

## Troubleshooting error for SSO Login

You might encounter an error message — “Something went wrong: please use the provider that you originally signed up with” — when you attempt to log in via SSO.

This error message indicates a conflict between your initial sign-up method and your attempt to log in via SSO after initially signing up for Baserow with a username and password.

Here are the primary options to address this error:

**Option 1: Enable multiple authentication methods**

Set the environment variable `BASEROW_ALLOW_MULTIPLE_SSO_PROVIDERS_FOR_SAME_ACCOUNT=true`. After setting this variable, restart the Baserow instance. This allows users to log in with either a password or SSO.

This option **increases security risk** , especially if you have multiple OAuth providers enabled. An attacker who gains access to a user’s account on any external provider could potentially use that access to log in to the associated Baserow account.

> For optimal security, we recommend maintaining consistent authentication methods unless necessary. If enabling multiple login methods is essential, implement additional security measures to mitigate potential risks.

**Option 2: Maintain consistent authentication method**

Users can continue logging in with the authentication method they signed up with. This avoids changing Baserow’s default behavior and maintains existing security measures.

**Option 3: Delete user from[Admin panel](/user-docs/enterprise-admin-panel) and re-login via SSO**

You can delete the user from the Baserow [admin panel](/user-docs/enterprise-admin-panel). Upon logging in via SSO, Baserow will recreate the user, automatically setting SSO as their default authentication method.

Deleting the user permanently removes all their associated data within Baserow. This option should only be considered if data loss is acceptable and after ensuring all data is backed up elsewhere.

Always prioritize data security when modifying your authentication settings.

## Related content

  * [Single Sign On (SSO) overview](/user-docs/single-sign-on-sso-overview).
  * [Baserow Enterprise plan](/user-docs/enterprise-license-overview).
  * [Enable SSO in the admin panel](/user-docs/enable-single-sign-on-sso).
  * [Email and password authentication](/user-docs/email-and-password-authentication).

