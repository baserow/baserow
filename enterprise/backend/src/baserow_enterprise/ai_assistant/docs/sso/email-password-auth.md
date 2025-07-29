# Baserow Documentation

Source: https://baserow.io/user-docs/email-and-password-authentication

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Email and Password Authentication

Baserow supports SSO for a [range of identity providers (IdP)](/user-docs/single-sign-on-sso-overview). SSO feature is a part of the Baserow Enterprise offering.

This article is intended for administrators who want to enable/disable email and password authentication.

## Disable password provider

Email and password authentication can be enabled or disabled from the Authentication page of the Admin Panel like other IdPs.

Before enabling/disabling email and password authentication via the admin panel, you must first enable an SSO identity provider. Learn more about [configuring SSO in the Admin Panel](/user-docs/enable-single-sign-on-sso).

> At least one auth provider has to be always enabled. If authentication with email/password is disabled, SAML or OAuth 2 provider needs to be configured. It is not possible to delete or disable the last enabled provider.

To disable Email and password authentication,

  1. Navigate to the Admin Panel.
  2. Click on the Authentication page in the navigation sidebar on the left. You should see a list of IdPs configured.
  3. Toggle the switch under "Email and password authentication” to enable or disable.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d0847ce8-ca7c-482b-a72f-0f99291e4202/Screenshot%202023-01-06%20at%2012.30.10.png)

Note that when password authentication is disabled, the login and sign up forms are hidden. If disabled, only an instance admin is allowed to log in with their email and password.

## Bypass login page redirect

> Note that this action is restricted to instance admins. An Instance Admin is the account that installs and sets up Baserow and has staff privileges.

Both SAML and OAuth2 providers work based on redirection to another site. If password authentication is disabled and only one redirect-based auth provider is enabled (SAML or OAuth 2), the login page will redirect users automatically. By default, the user will see the login page only for a brief moment before it redirects.

However, the instance admin (super admin) can always log in via email and password even when the Email and password authentication is disabled and the automatic redirect is in action.

If the login form is hidden, the instance admin can bypass this automatic redirect behavior on the login page by adding the `?noredirect` parameter to the login URL.

The instance admin can use this `?noredirect` URL parameter to actually display the login page and log in via email and password.

The full URL in the SaaS hosted version would look like: `https://baserow.io/login?noredirect`

This is helpful so that instance admins know how to log in to Baserow if their SAML or OAuth provider is misconfigured and email/password auth is disabled. If the password authentication is enabled, the login page will never redirect and all users can log in with their details.

## Related content

  * [Single Sign On (SSO) overview](/user-docs/single-sign-on-sso-overview).
  * [Enable SSO in the admin panel](/user-docs/enable-single-sign-on-sso).
  * [Baserow Enterprise plan](/user-docs/enterprise-license-overview).

