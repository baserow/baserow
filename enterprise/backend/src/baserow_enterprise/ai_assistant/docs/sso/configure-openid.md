# Baserow Documentation

Source: https://baserow.io/user-docs/configure-openid-connect-for-oauth-2-sso

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Configure OpenID Connect for OAuth 2 SSO

This guide is intended for [Admins](/user-docs/working-with-collaborators#set-the-permission-level-for-collaborators) setting up OAuth 2 SSO with OpenID Connect.

OpenID Connect (OIDC) is an open authentication protocol on top of the OAuth 2.0 framework. OIDC is a consumer-focused standard that enables users to access third-party websites with just one sign-on (SSO).

> Single Sign-On feature is a part of the Baserow Enterprise offering. Instance-wide features are only available on the self-hosted Enterprise plan. To learn more about the Baserow enterprise plan, [visit our pricing page](/pricing).

If you are looking for information on setting up SSO with other providers:

  * [Configure Azure AD for SAML SSO](/user-docs/configure-sso-with-azure-ad)
  * [Configure OneLogin for SAML SSO](/user-docs/configure-sso-with-onelogin)
  * [Configure Okta for SAML SSO](/user-docs/configure-sso-with-okta)
  * [Configure Google for OAuth 2 SSO](/user-docs/configure-google-for-oauth-2-sso)
  * [Configure Facebook for OAuth 2 SSO](/user-docs/configure-facebook-for-oauth-2-sso)
  * [Configure GitHub for OAuth 2 SSO](/user-docs/configure-github-for-oauth-2-sso)
  * [Configure GitLab for OAuth 2 SSO](/user-docs/configure-gitlab-for-oauth-2-sso)

When you configure Single Sign-on (SSO) with OpenID Connect, your users can create and sign into their Baserow accounts using OpenID Providers (OPs) such as an email service or social network to verify their identities.

Based on the authentication carried out by an authorization server, you can receive basic profile information about the end user and validate the end user’s identity.

Here’s how to set up OAuth 2 SSO with OpenID Connect to sign in to your Baserow account.

## Set up OAuth 2 SSO with OpenID Connect

Sign in or create an account with a provider of your choice.

You must register your application with the IdP in order to let users log in using an OIDC Identity Provider. To do this, you must refer to the documentation provided by your IdP as it differs for each OIDC Identity Provider.

Your OIDC Identity Provider will create a unique ID for the registered API during this procedure, typically referred to as a Client ID and Secret.

Once created, you will use the credentials to configure a new OpenID Connect provider in Baserow:

  * Obtain the Provider’s Base URL.
  * Obtain the Provider’s Client ID.
  * Obtain the Provider’s Client Secret.
  * Set Redirect URL. This is the Baserow Callback URL you will find in the Baserow Provider Settings where you create or edit the authentication provider.

After you’ve accessed this information from the application, copy and paste the information from OpenID Connect into Baserow.

## Connect OpenID Connect to your Baserow Account

Log in to Baserow. Go to Admin > Authentication > Provider. Retrieve your _**Callback URL**_ from your Baserow admin settings modal, following the [steps in this guide](/user-docs/enable-single-sign-on-sso#oauth-provider-configuration).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/ea05ea09-eecf-4ca3-8171-5162d76a30f4/Screenshot_2022-11-07_at_16.02.14.png)

Configure OpenID Connect by inputting the URL, Client ID and Secret information into the corresponding fields in your Baserow Admin Dashboard, following the [steps in this guide](/user-docs/enable-single-sign-on-sso#oauth-provider-configuration).

You should be able to log in with OpenID Connect after completing these steps by visiting your Baserow servers login page. Your users will now be taken to an OpenID Connect sign-in flow when they attempt to log into Baserow. After logging in with their OpenID Connect credentials, they will be redirected to the app.

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

