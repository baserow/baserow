# Baserow Documentation

Source: https://baserow.io/user-docs/configure-sso-with-okta

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Configure SSO with Okta

This guide is intended for [Admins](/user-docs/working-with-collaborators#set-the-permission-level-for-collaborators) setting up SSO SAML with Okta.

When you configure Single Sign-on (SSO) with Okta, your users will be able to create and sign into their Baserow accounts using Okta.

If you are looking for information on setting up SSO with other providers:

  * [Configure Azure AD for SAML SSO](/user-docs/configure-sso-with-azure-ad)
  * [Configure OneLogin for SAML SSO](/user-docs/configure-sso-with-onelogin)
  * [Configure Google for OAuth 2 SSO](/user-docs/configure-google-for-oauth-2-sso)
  * [Configure Facebook for OAuth 2 SSO](/user-docs/configure-facebook-for-oauth-2-sso)
  * [Configure GitHub for OAuth 2 SSO](/user-docs/configure-github-for-oauth-2-sso)
  * [Configure GitLab for OAuth 2 SSO](/user-docs/configure-gitlab-for-oauth-2-sso)
  * [Configure OpenID Connect for OAuth 2 SSO](/user-docs/configure-openid-connect-for-oauth-2-sso)

> Single Sign-On feature is a part of the Baserow Enterprise offering. Instance-wide features are only available on the self-hosted Enterprise plan. To learn more about the Baserow enterprise plan, [visit our pricing page](/pricing).

Here’s how to set up Okta to sign in to your Baserow account.

## Set up SSO SAML with OneLogin

To get started, log into your Okta account and click **Admin** in the top right corner:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/7e8f8d96-a885-452e-82b2-a97d8777a409/Screenshot_2022-11-04_at_06.30.49.png)

Click the **Applications** tab in the sidebar on the Okta admin page, then select the **Applications** option from the dropdown menu.

Next, click the `Create App Integration` button on the Applications page:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/8a72703c-84ed-4ff2-b5a5-655f9bc53299/Screenshot_2022-11-01_at_12.42.02.png)

Choose SAML 2.0 as the sign-in method:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2ce28b13-2655-4551-a7cb-7fbb75a28fbb/Screenshot_2022-11-01_at_12.42.15.png)

Choose **Baserow** as the app name and upload the logo for the application:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/8149d6e0-138a-476e-808d-aeeabebb881c/Screenshot_2022-11-01_at_12.42.43.png)

Next, retrieve your _**Default Relay State URL**_ and _**Single Sign On URL**_ from the admin settings modal in Baserow, following the [steps in this guide](/user-docs/enable-single-sign-on-sso#add-providers-for-sso-saml).

To Configure SAML in Okta, add your `Single Sign On URL` in the first two fields (”Single sign on URL” and “Audience URI (SP Entity ID)”).

Add your `Default Relay State URL` in the “Default Relay State” field.

Create 3 attribute statements with values as such:

Field name | Value  
---|---  
user.email | user.email  
user.first_name | user.firstName  
user.last_name | user.lastName  
  
Set all other fields like in the image below:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/f8d9c159-0159-45b2-a6b1-404faceb8cdf/Screenshot_2022-11-01_at_12.44.23.png)

Click ‘**Next** ’ to complete the configuration.

Once the app has been created, assign it to people from the ‘Assignments’ tab of the Baserow Okta application. This permits these people to send the user information from Okta to Baserow to create/log in to the account.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/07c31b77-a626-4db5-a95e-f6ab7d76cd2e/Screenshot_2022-11-01_at_12.45.59.png)

To ensure that the sign in works properly on Baserow, set the email domain associated with this app and paste the Identity provider metadata into Baserow.

The metadata can be found in the ‘Sign On’ tab. Scroll to “SAML Signing Certificates” section and then choose a certificate type with active status. From the actions dropdown of the active certificate, click “View IdP metadata”.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/bf108d7c-a40e-4acc-b484-245bc2622f23/Screenshot_2022-11-01_at_12.44.58.png)

After you’ve accessed the information from the IdP Metadata, copy and paste the information from Okta into Baserow.

## Connect Okta to your Baserow Account

Head back to Baserow Admin > Authentication > Provider.

Configure OneLogin by inputting the domain and metadata information into the corresponding fields in your Baserow Admin Dashboard, following the [steps in this guide](/user-docs/enable-single-sign-on-sso#add-providers-for-sso-saml).

You should be able to log in with OneLogin after completing these steps by visiting your Baserow server login page. Your users will now be taken to a OneLogin sign-in flow when they attempt to log into Baserow. After logging in with their OneLogin credentials, they will be redirected to the app.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/a3fc6ba7-66b4-47d2-a09c-c62d321d5407/Screenshot_2022-11-04_at_07.02.25.png)

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

