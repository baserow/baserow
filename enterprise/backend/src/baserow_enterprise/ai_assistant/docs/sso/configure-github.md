# Baserow Documentation

Source: https://baserow.io/user-docs/configure-github-for-oauth-2-sso

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Configure GitHub for OAuth 2 SSO

This guide is intended for [Admins](/user-docs/working-with-collaborators#set-the-permission-level-for-collaborators) setting up OAuth 2 SSO with GitHub.

When you configure Single Sign-on (SSO) with GitHub, your users will be able to create and sign into their Baserow accounts using GitHub.

If you are looking for information on setting up SSO with other providers:

  * [Configure Azure AD for SAML SSO](/user-docs/configure-sso-with-azure-ad)
  * [Configure OneLogin for SAML SSO](/user-docs/configure-sso-with-onelogin)
  * [Configure Okta for SAML SSO](/user-docs/configure-sso-with-okta)
  * [Configure Google for OAuth 2 SSO](/user-docs/configure-google-for-oauth-2-sso)
  * [Configure Facebook for OAuth 2 SSO](/user-docs/configure-facebook-for-oauth-2-sso)
  * [Configure GitLab for OAuth 2 SSO](/user-docs/configure-gitlab-for-oauth-2-sso)
  * [Configure OpenID Connect for OAuth 2 SSO](/user-docs/configure-openid-connect-for-oauth-2-sso)

> Single Sign-On feature is a part of the Baserow Enterprise offering. Instance-wide features are only available on the self-hosted Enterprise plan. To learn more about the Baserow enterprise plan, [visit our pricing page](/pricing).

Here’s how to set up OAuth 2 SSO with GitHub to sign in to your Baserow account.

## Set up OAuth 2 SSO with GitHub

Sign in or create a GitHub account. Go to Settings → Developer settings → OAuth Apps at <https://github.com/settings/developers>.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/3c3c7900-28ae-4d65-a04e-75234f5788f8/Screenshot_2022-11-07_at_15.01.41.png)

Create a new OAuth application in GitHub by clicking the **Register a new application** button.

In the new OAuth application on GitHub,

  1. Input the Application name as “Baserow”.
  2. Input the Homepage URL. This will be your public Baserow URL.
  3. Input the Authorization callback URL. This is the Baserow Callback URL in the Baserow Provider Settings where you create or edit the authentication provider.

Log in to Baserow. Go to Admin > Authentication > Provider. Retrieve your _**Callback URL**_ from your Baserow admin settings modal, following the [steps in this guide](/user-docs/enable-single-sign-on-sso#oauth-provider-configuration).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/83857cd9-ee3a-4ea7-a21c-f4fd69acbc17/Screenshot_2022-11-07_at_15.08.01.png)

  4. Click the **Register application** button to save your changes.

  5. To integrate Baserow with GitHub, generate a new secret by clicking on **Generate a new client secret** button.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/19e21f07-dcb5-4710-9321-cbcd15e9ff12/Screenshot_2022-11-07_at_15.10.10.png)

  6. Once created, use the credentials to configure a new GitHub provider in Baserow:

  * Client ID is the Baserow Client ID.
  * Client secret is the Baserow Secret.

![Create a new OAuth application in GitHub](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/457c10f1-e480-4132-b7aa-053d274d8907/Screenshot%202023-07-18%20at%2011.07.05.png)

After you’ve accessed this information from the application, copy and paste the information from GitHub into Baserow.

## Connect GitHub to your Baserow Account

Head back to Baserow Admin > Authentication > Provider.

To set up GitHub integration, simply enter your _Client ID_ and _Secret_ information into the designated fields in your Baserow Admin Dashboard. [Follow the steps outlined in our guide](/user-docs/enable-single-sign-on-sso#oauth-provider-configuration).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/da1f821b-4cbb-429b-bcc6-2c186d601825/Screenshot_2022-11-07_at_15.11.46.png)

You should be able to log in to Baserow with GitHub after completing these steps. Simply visit your Baserow server’s login page, and you’ll find the option to log in with GitHub.

When your users try to access Baserow, they’ll be seamlessly redirected to GitHub’s sign-in flow. After securely logging in with their GitHub credentials, they’ll be redirected back to the Baserow app.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/1cd2f1db-be25-4953-be00-76605aab583e/Screenshot_2022-11-07_at_15.12.42.png)

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

