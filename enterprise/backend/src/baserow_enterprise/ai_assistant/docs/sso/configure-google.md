# Baserow Documentation

Source: https://baserow.io/user-docs/configure-google-for-oauth-2-sso

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Configure Google for OAuth 2 SSO

This guide is intended for [Admins](/user-docs/working-with-collaborators#set-the-permission-level-for-collaborators) setting up OAuth 2 SSO with Google.

When you configure Single Sign-on (SSO) with Google, your users will be able to create and sign into their Baserow accounts using Google.

If you are looking for information on setting up SSO with other providers:

  * [Configure Azure AD for SAML SSO](/user-docs/configure-sso-with-azure-ad)
  * [Configure OneLogin for SAML SSO](/user-docs/configure-sso-with-onelogin)
  * [Configure Okta for SAML SSO](/user-docs/configure-sso-with-okta)
  * [Configure Facebook for OAuth 2 SSO](/user-docs/configure-facebook-for-oauth-2-sso)
  * [Configure GitHub for OAuth 2 SSO](/user-docs/configure-github-for-oauth-2-sso)
  * [Configure GitLab for OAuth 2 SSO](/user-docs/configure-gitlab-for-oauth-2-sso)
  * [Configure OpenID Connect for OAuth 2 SSO](/user-docs/configure-openid-connect-for-oauth-2-sso)

> Single Sign-On feature is a part of the Baserow Enterprise offering. Instance-wide features are only available on the self-hosted Enterprise plan. To learn more about the Baserow enterprise plan, [visit our pricing page](/pricing).

Here’s how to set up OAuth 2 SSO with Google to sign in to your Baserow account.

## Set up OAuth 2 SSO with Google

Sign in or create a Google account then sign into Google Cloud Console at <https://console.cloud.google.com/>.

Create a new project or select an existing project in your organization:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/800b03b7-e3af-4f35-9369-89988389bfc0/Screenshot_2022-11-04_at_12.12.23.png)

Go to API & Services → Credentials:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/4ff73925-a71e-483c-9377-b757936f151e/4383a565339f10ee5cd4bf6097005a9938b90525.webp)

Next, log in to Baserow. Go to the Admin > Authentication > Provider. Retrieve your _**Callback URL**_ from your Baserow admin settings modal, following the [steps in this guide](/user-docs/enable-single-sign-on-sso#oauth-provider-configuration).

Create a new credential for OAuth Client ID. A client ID is used to identify a single app to Google’s OAuth servers.

  * Choose _**Web application**_ as the Application type.
  * Fill in Name.
  * Add a URI under Authorized redirect URIs. This is the Baserow Callback URL you will find in the Baserow Provider Settings where you create or edit the authentication provider.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/16ffcb4c-5119-4e2e-8f5b-886e16581bb8/Screenshot_2022-11-04_at_14.17.36.png)

Click the ‘Create’ button.

Once created, you will be able to obtain Client ID and Client secret:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/ef63b71e-7557-40df-9348-40e00455e8c1/Screenshot_2022-11-04_at_14.18.36.png)

After you’ve accessed the information from the Credentials, copy and paste the information from Google into Baserow.

## Connect Google to your Baserow Account

Head back to Baserow Admin > Authentication > Provider.

Configure Google by inputting the Client ID and secret information into the corresponding fields in your Baserow Admin Dashboard, following the [steps in this guide](/user-docs/enable-single-sign-on-sso#oauth-provider-configuration).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/e1b155da-fffb-465f-83a1-1186f0d02831/Screenshot_2022-11-07_at_15.30.58.png)

You should be able to log in with Google after completing these steps by visiting your Baserow servers login page. Your users will now be taken to a Google sign-in flow when they attempt to log into Baserow. After logging in with their Google credentials, they will be redirected to the app.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/3a831490-1029-4c54-b8d1-3484761dfea3/Screenshot_2022-11-04_at_14.48.37.png)

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

