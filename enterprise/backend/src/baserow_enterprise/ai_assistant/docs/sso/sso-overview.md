# Baserow Documentation

Source: https://baserow.io/user-docs/single-sign-on-sso-overview

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Single Sign On (SSO) overview

Single Sign On (SSO) allows users to log in just one time with one set of credentials to get access to all corporate apps, websites, and data for which they have permission.

Baserow integrates with any 3rd party SSO provider using Security Assertion Markup Language (SAML) to control who can log in and let them do so without having to sign-up to your Baserow separately.

> Single Sign-On feature is a part of the Baserow Enterprise offering. Instance-wide features are only available on the self-hosted Enterprise plan. To learn more about the Baserow enterprise plan, [visit our pricing page](/pricing).

Only Instance admins have access to the Baserow Admin panel. Instance Admins have staff access to the entire self-hosted instance.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d58ccccd-1a15-4563-82b8-b0f02afae076/Untitled.png)

Baserow Users can use Single Sign On (SSO) to maintain their user identities in a central location so they can access many services using the same user base.

## Prerequisites

In general, to configure an authentication provider for single-sign-on users will need to:

  * Obtain Client ID and Secret from your provider of choice and use them to create a new authentication provider in Baserow.
  * Know the provider’s base URL for GitLab or OpenID Connect providers.
  * Set/allow the Baserow Callback URL in your provider so that users can be safely redirected back to Baserow upon login.

## View a list of authentication providers

To view the providers registered in your instance:

  1. Visit your Baserow server and log in as an instance-wide admin.
  2. In the left menu, select **Admin**.
  3. Click the **Authentication** page. The Authentication providers pane opens and displays a list of the providers in your server.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/c21df210-ed52-45d1-bcff-943468ac48dc/Screenshot%202023-02-15%20at%2009.37.24.png)

## SAML SSO Providers

Security Assertion Markup Language (SAML) is a security standard for managing authentication and access. When using SAML SSO, users can log in to their Baserow organization using the organization’s identity provider.

Baserow supports dedicated integrations with the following identity providers:

  * [Set up SSO for Okta](/user-docs/configure-sso-with-okta)
  * [Set up SSO for OneLogin](/user-docs/configure-sso-with-onelogin)
  * [Set up SSO for Azure AD](/user-docs/configure-sso-with-azure-ad)

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/eb37acf4-c48f-4c77-ae46-2448b3b1f807/Untitled%201.png)

## OAuth 2 SSO Providers

OAuth2 protocol provides secure delegated access without sharing the credentials. It allows users to give access to their resources hosted by a service provider, such as Facebook, without giving away credentials. It acts as an intermediary on behalf of the end user, providing the service with an access token that authorizes specific account information to be shared.

  * [Configure Google provider](/user-docs/configure-google-for-oauth-2-sso)
  * [Configure Facebook provider](/user-docs/configure-facebook-for-oauth-2-sso)
  * [Configure GitHub provider](/user-docs/configure-github-for-oauth-2-sso)
  * [Configure GitLab provider](/user-docs/configure-gitlab-for-oauth-2-sso)

## OpenID Connect SSO

OpenID Connect is an identity layer built on top of the OAuth 2.0 protocol. Its purpose is to give you one login for multiple sites. With the support of OpenID Connect, the Baserow users are now able to use ANY service that supports this exact protocol to login into the tool.

  * [Set up SSO for OpenID Connect](/user-docs/configure-openid-connect-for-oauth-2-sso)

## Related content

  * [Baserow Enterprise plan](/user-docs/enterprise-license-overview).
  * [Enable SSO in the admin panel](/user-docs/enable-single-sign-on-sso).
  * [Email and password authentication](/user-docs/email-and-password-authentication).

