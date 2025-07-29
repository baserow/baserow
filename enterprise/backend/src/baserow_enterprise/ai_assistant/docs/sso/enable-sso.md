# Baserow Documentation

Source: https://baserow.io/user-docs/enable-single-sign-on-sso

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Enable SSO in the admin panel

Streamline your login process with Single Sign-On (SSO), which enables users to log in once using a single set of credentials. With SSO, you can conveniently access all corporate applications, websites, and authorized data. Make the most of your Baserow experience by simplifying authentication and securely accessing your resources.

Learn how to integrate SSO to seamlessly authenticate across various applications and systems without the need to remember multiple usernames and passwords.

## Overview

Instance Admins can set up Single sign-on (SSO) with Identity Providers (IdP) for their teams’ logins to Baserow.

> Single Sign-On feature is a part of the Baserow Enterprise offering. Instance-wide features are only available on the self-hosted Enterprise plan. To learn more about the Baserow enterprise plan, [visit our pricing page](/pricing).

Only Instance admins on a self-hosted Baserow server with the Enterprise plan can access the SSO admin page. Instance Admins have staff access to the entire self-hosted instance.

## Add providers for SSO SAML

Baserow uses SAML (Security Assertion Markup Language) to simplify and secure the authentication process so users only need to log in once with a single set of authentication credentials.

  1. From your Baserow dashboard, go to Admin → Authentication in the navigation sidebar on the left. Under the authentication configuration section, click the “Add Provider” button.

  2. Select “SSO SAML Provider” from the dropdown menu. Clicking this will open up a configuration window:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/fbb90e5c-15ae-41e4-ab1e-7991449524b6/Screenshot_2022-11-03_at_14.02.00.png)

  3. When the “Add a new SSO SAML provider” modal is opened, you can see the `Default Relay State URL` and the `Single Sign On URL` needed to configure a SAML application. You’ll need this value later, so make a note of them.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b73f76eb-3286-4c13-8fa8-597bbec339b6/Screenshot_2022-11-01_at_12.39.19.png)

  4. Next, retrieve your third-party SSO metadata and domain from your SSO identity provider, following the instructions for each in this guide:

     * [Configure OneLogin for SAML SSO](/user-docs/configure-sso-with-onelogin)
     * [Configure Okta for SAML SSO](/user-docs/configure-sso-with-okta)
     * [Configure Azure AD for SAML SSO](/user-docs/configure-sso-with-azure-ad)
  5. Paste the XML metadata in the authentication popup. You’ll end up with something like this:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/874d2487-8e4e-432f-a0ec-106bc51e5066/Screenshot_2022-11-01_at_16.11.29.png)

  6. Save the new provider. Click ‘Create’ to allow the SSO login configuration to occur.

After the provider has been correctly created, you should see it listed in the provider’s list.

## OAuth provider configuration

Baserow supports a variety of OAuth 2 providers like Google, Facebook, GitLab, GitHub, and any providers that support OpenID Connect protocol.

  1. From your Baserow dashboard, go to Admin → Authentication. Under the authentication configuration section, click the “Add Provider” button.

  2. Select a provider from the dropdown menu. Clicking this will open up a configuration window:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b131496a-ee16-4322-b0a1-294f46afe1d2/Screenshot_2022-11-04_at_12.36.58.png)

  3. When the modal is opened, you can see the **Callback URL** needed to configure the provider. You’ll need this value later, so make a note of it.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/8f6162b6-145d-4545-a6a3-26c443fd2d5f/Screenshot_2022-11-04_at_12.42.36.png)

  4. Next, retrieve your **Client ID** and **Secret** from the provider, following the instructions for each in this guide:

     * [Configure SSO with Google as the Identity Provider](/user-docs/configure-google-for-oauth-2-sso)
     * [Configure SSO with Facebook as the Identity Provider](/user-docs/configure-facebook-for-oauth-2-sso)
     * [Configure SSO with GitHub as the Identity Provider](/user-docs/configure-github-for-oauth-2-sso)
     * [Configure SSO with GitLab as the Identity Provider](/user-docs/configure-gitlab-for-oauth-2-sso)
     * [Configure SSO with OpenID Connect](/user-docs/configure-gitlab-for-oauth-2-sso)

To configure OpenID Connect, you will also need to retrieve your **Custom provider name** and **Base URL** from the provider.

  5. After retrieving your organization’s third-party SSO details, you will need to enter the provider’s **Client ID** and **Secret** that you receive from the IdP in the fields in Baserow.

     * Fill in the Provider’s name. This name will be displayed to your Baserow users on the login screen.
     * Fill in the **Client ID** and **Secret** that you obtained from the provider.
     * To configure OpenID Connect, also fill in the Provider’s Base **URL**. Also, you can optionally set a custom GitLab **URL** in case you are self-hosting GitLab.
  6. Save the new provider. Click ‘Create’ to allow the SSO login configuration to occur.

After the provider has been correctly created, you should see it listed in the provider’s list.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/7ac014e5-12ed-4883-b281-9d7603bbc6c3/Screenshot%202023-01-06%20at%2012.30.10.png)

## Edit or delete an identity provider

On your authentication page in the admin section, you can edit, delete or disable an authentication provider.

Any IdP, including Email and Password authentication, can be disabled/enabled, but at least one provider needs to be enabled. To disable or enable an authentication provider, use the toggle beside the provider.

> If authentication with Email and Password is disabled, at least one authentication provider must always be enabled. It is not possible to delete or disable the last enabled provider.

To edit or delete an authentication provider, click the ellipsis icon beside the provider and select _Edit_ or _Delete:_

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d1a6cfe7-b770-4e85-84c8-cb8fb6e3198c/Screenshot_2022-11-04_at_08.12.21.png)

## Related content

  * [Single Sign On (SSO) overview](/user-docs/single-sign-on-sso-overview).
  * [Baserow Enterprise plan](/user-docs/enterprise-license-overview).
  * [Email and password authentication](/user-docs/email-and-password-authentication).

