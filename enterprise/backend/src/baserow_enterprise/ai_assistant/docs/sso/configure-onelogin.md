# Baserow Documentation

Source: https://baserow.io/user-docs/configure-sso-with-onelogin

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Configure SSO with OneLogin

This guide is intended for [Admins](/user-docs/working-with-collaborators#set-the-permission-level-for-collaborators) setting up SSO SAML with OneLogin. OneLogin is a cloud-based identity and access management solution.

When you configure Single Sign-on (SSO) with OneLogin, your users will be able to create and sign into their Baserow accounts using OneLogin.

If you are looking for information on setting up SSO with other providers:

  * [Configure Azure AD for SAML SSO](/user-docs/configure-sso-with-azure-ad)
  * [Configure Okta for SAML SSO](/user-docs/configure-sso-with-okta)
  * [Configure Google for OAuth 2 SSO](/user-docs/configure-google-for-oauth-2-sso)
  * [Configure Facebook for OAuth 2 SSO](/user-docs/configure-facebook-for-oauth-2-sso)
  * [Configure GitHub for OAuth 2 SSO](/user-docs/configure-github-for-oauth-2-sso)
  * [Configure GitLab for OAuth 2 SSO](/user-docs/configure-gitlab-for-oauth-2-sso)
  * [Configure OpenID Connect for OAuth 2 SSO](/user-docs/configure-openid-connect-for-oauth-2-sso)

> Single Sign-On feature is a part of the Baserow Enterprise offering. Instance-wide features are only available on the self-hosted Enterprise plan. To learn more about the Baserow enterprise plan, [visit our pricing page](/pricing).

Here’s how to set up OneLogin to sign in to your Baserow account.

## Set up SSO SAML with OneLogin

Log in to your [OneLogin](https://www.onelogin.com) account as an administrator. Click **Administration** on the toolbar to go to the Admin panel.

To add apps to your company app catalog, go to **Applications > Applications** from the admin page then click on `Add App`:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b29a4448-f4eb-473e-a00d-54548c33d5b7/Screenshot_2022-11-01_at_16.19.54.png)

Search and select the _SAML Custom Connector (Advanced)_ :

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/3e2dfd17-3092-4b10-9073-0e82b90bfebc/Screenshot_2022-11-01_at_16.54.27.png)

Enter _Baserow_ as the **Display Name** of the new app, and make sure **Visible in portal** is on. Upload icon and add a description to the new SAML connector.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b8450668-0805-48a4-979a-8eaa8bd4fc2f/Screenshot_2022-11-01_at_16.55.02.png)

Click **Save.** You’ll find a new left-side navigation menu after saving. Click **Configuration** in the sidebar menu.

Next, log in to Baserow. Go to the Admin > Authentication > Provider. Retrieve your _**Default Relay State URL**_ and _**Single Sign On URL**_ from your Baserow admin settings modal, following the [steps in this guide](/user-docs/enable-single-sign-on-sso#add-providers-for-sso-saml).

In OneLogin configuration tab, paste your Baserow `Default Relay State URL` in the `RelayState` field.

Paste your `Single Sign On URL` in the next four fields as shown below.

Baserow value | Corresponding OneLogin Configuration field  
---|---  
Default Relay State URL | RelayState  
Single Sign On URL | Audience (EntityID)  
Single Sign On URL | Recipient  
Single Sign On URL | ACS (Consumer) URL Validator*  
Single Sign On URL | ACS (Consumer) URL*  
  
Convert your  _**Single Sign On URL**_ into a regular expression and paste that into the **ACS (Consumer) URL Validator** * field. For information on regular expression, [visit this link](https://onelogin.service-now.com/support?sys_id=93f95543db109700d5505eea4b96198f&view=sp&id=kb_article&table=kb_knowledge). Add the required symbols in the ACS (Consumer) URL Validator* field as shown in the picture below to make it a valid regex:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/6d4620c2-4270-4575-95ca-ebd480f1931b/Screenshot_2022-11-01_at_16.56.20.png)

Set the next set of configuration fields as shown below:

OneLogin field | Value  
---|---  
SAML initiator | OneLogin  
SAML nameID format | Email  
SAML issuer type | Specific  
SAML signature element | Both  
SAML encryption method | AES-128-CBC  
Generate AttributeValue tag for empty values | ☑  
SAML sessionNotOnOrAfter | 1140  
  
![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/764d7e2c-5f84-4c31-b377-8be6d50bdc6c/Screenshot_2022-11-01_at_16.56.40.png)

Once you’re done, click **Save** to store the app settings.

After saving, click on the **Parameters** tab. Then, click the + icon to add 3 custom parameters.

Assign the following field names and check **Include in SAML assertion. Click **Save** to go to the next screen then select the corresponding values from the dropdown:

Field name | Value  
---|---  
user.email | Email  
user.first_name | First Name  
user.last_name | Last Name  
  
Set the parameters that will be sent in the SAML response with values as shown below:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/0de4ee4c-c559-49ad-8a7a-de148098750f/Screenshot_2022-11-01_at_16.56.50.png)

Once you’re done, click **Save**.

To configure the SAML provider in Baserow, you’ll need to download the SAML metadata from the “More Actions” menu in the _Applications_ tab as shown below:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/57d65bd5-52bb-4400-8b75-e9a8684e9a5d/Screenshot_2022-11-01_at_16.57.46.png)

After you’ve accessed the information from the SAML Metadata, copy and paste the information from OneLogin into Baserow.

## Connect OneLogin to your Baserow Account

Head back to Baserow Admin > Authentication > Provider.

Configure OneLogin by inputting the domain and metadata information into the corresponding fields in your Baserow Admin Dashboard, following the [steps in this guide](/user-docs/enable-single-sign-on-sso#add-providers-for-sso-saml).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/43422ceb-7dd3-42e9-894e-3fa8ce3d2137/Screenshot_2022-11-07_at_12.11.42.png)

You should be able to log in with OneLogin after completing these steps by visiting your Baserow servers login page. Your users will now be taken to a OneLogin sign-in flow when they attempt to log into Baserow. After logging in with their OneLogin credentials, they will be redirected to the app.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/38b75bc5-cd9a-48f7-a34d-38106358a570/Screenshot_2022-11-07_at_12.12.43.png)

## Add users to access OneLogin

You can grant your users access to the newly created application, either by adding to individual Users or by adding to Roles or Workspaces within OneLogin, depending on how you prefer to manage your Users there.

To add users to this application, click on **Users** in the top bar menu item.

Go to **Users > Users** and click the **New User** button to open the **User Info** page. On the **User Info** page, verify that the user is activated. Enter the user’s name and email address, along with any other personal information you want to include. Click the **Save User** button.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/141ffccd-2ce0-41b9-b5af-74a8fab538db/Screenshot_2022-11-07_at_12.18.17.png)

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

