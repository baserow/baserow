# Baserow Documentation

Source: https://baserow.io/user-docs/configure-gitlab-for-oauth-2-sso

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Configure GitLab for OAuth 2 SSO

This guide is intended for [Admins](/user-docs/working-with-collaborators#set-the-permission-level-for-collaborators) setting up OAuth 2 SSO with GitLab.

When you configure Single Sign-on (SSO) with GitLab, your users will be able to create and sign into their Baserow accounts using GitLab.

If you are looking for information on setting up SSO with other providers:

  * [Configure Azure AD for SAML SSO](/user-docs/configure-sso-with-azure-ad)
  * [Configure OneLogin for SAML SSO](/user-docs/configure-sso-with-onelogin)
  * [Configure Okta for SAML SSO](/user-docs/configure-sso-with-okta)
  * [Configure Google for OAuth 2 SSO](/user-docs/configure-google-for-oauth-2-sso)
  * [Configure Facebook for OAuth 2 SSO](/user-docs/configure-facebook-for-oauth-2-sso)
  * [Configure GitHub for OAuth 2 SSO](/user-docs/configure-github-for-oauth-2-sso)
  * [Configure OpenID Connect for OAuth 2 SSO](/user-docs/configure-openid-connect-for-oauth-2-sso)

> Single Sign-On feature is a part of the Baserow Enterprise offering. Instance-wide features are only available on the self-hosted Enterprise plan. To learn more about the Baserow enterprise plan, [visit our pricing page](/pricing).

Here’s how to set up OAuth 2 SSO with GitLab to sign in to your Baserow account.

## Set up OAuth 2 SSO with GitLab

Sign in or create a [GitLab](https://about.gitlab.com/) account. Go to User settings → Applications at <https://gitlab.com/-/profile/applications>.

Add a new application:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/64147fe6-1fa4-44bf-b21b-bb3e080d42b5/Screenshot_2022-11-07_at_15.21.47.png)

Next, log in to Baserow. Go to the Admin > Authentication > Provider. Retrieve your _**Callback URL**_ from your Baserow admin settings modal, following the [steps in this guide](/user-docs/enable-single-sign-on-sso#oauth-provider-configuration).

To set up the new application,

  * Fill in the Application name as **Baserow**
  * Fill in the Redirect URI. This is the Baserow Callback URL you will find in the Baserow Provider Settings where you create or edit the authentication provider.
  * Set the Confidential checkbox.
  * Allow the `read_user` scope.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/020644ba-019d-45fc-96be-3a723bad606d/Screenshot_2022-11-07_at_15.25.26.png)

Click the **Save application** button.

Once created, you will use the credentials to configure a new GitLab provider in Baserow:

  * Application ID is the Baserow Client ID.
  * Secret is the Baserow Secret.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b5db7f64-d64a-440d-9942-e8dc61675337/Screenshot_2022-11-07_at_15.28.19.png)

After you’ve accessed this information from the application, copy and paste the information from GitLab into Baserow.

## Connect GitLab to your Baserow Account

Head back to Baserow Admin > Authentication > Provider.

Configure GitLab by inputting the Client ID and secret information into the corresponding fields in your Baserow Admin Dashboard, following the [steps in this guide](/user-docs/enable-single-sign-on-sso#oauth-provider-configuration).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/f9e2b6f4-8ac0-4a8c-86f7-513f1f0a218e/Screenshot_2022-11-07_at_15.30.00.png)

You should be able to log in with GitLab after completing these steps by visiting your Baserow servers login page. Your users will now be taken to a GitLab sign-in flow when they attempt to log into Baserow. After logging in with their GitLab credentials, they will be redirected to the app.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/55cecad5-0a22-4586-a7af-a3b89924fe46/Screenshot_2022-11-07_at_15.30.34.png)

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

