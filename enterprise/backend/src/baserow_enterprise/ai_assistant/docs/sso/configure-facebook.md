# Baserow Documentation

Source: https://baserow.io/user-docs/configure-facebook-for-oauth-2-sso

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Configure Facebook for OAuth 2 SSO

This guide is intended for [Admins](/user-docs/working-with-collaborators#set-the-permission-level-for-collaborators) setting up OAuth 2 SSO with Facebook.

When you configure Single Sign-on (SSO) with Facebook, your users will be able to create and sign into their Baserow accounts using Facebook.

If you are looking for information on setting up SSO with other providers:

  * [Configure Azure AD for SAML SSO](/user-docs/configure-sso-with-azure-ad)
  * [Configure OneLogin for SAML SSO](/user-docs/configure-sso-with-onelogin)
  * [Configure Okta for SAML SSO](/user-docs/configure-sso-with-okta)
  * [Configure Google for OAuth 2 SSO](/user-docs/configure-google-for-oauth-2-sso)
  * [Configure GitHub for OAuth 2 SSO](/user-docs/configure-github-for-oauth-2-sso)
  * [Configure GitLab for OAuth 2 SSO](/user-docs/configure-gitlab-for-oauth-2-sso)
  * [Configure OpenID Connect for OAuth 2 SSO](/user-docs/configure-openid-connect-for-oauth-2-sso)

> Single Sign-On feature is a part of the Baserow Enterprise offering. Instance-wide features are only available on the self-hosted Enterprise plan. To learn more about the Baserow enterprise plan, [visit our pricing page](/pricing).

Here’s how to set up OAuth 2 SSO with Facebook to sign in to your Baserow account.

## Set up OAuth 2 SSO with Facebook

Sign in or create a Facebook account then sign in to Meta for Developers apps at <https://developers.facebook.com/apps/>.

Create a new app or select an existing app:

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/7b10cf62-2b6a-427a-a369-519d3c4d1937/Screenshot_2022-11-07_at_14.14.23.png)

Choose the _Business app_ type or another type that works for you. The app type can’t be changed after your app is created.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/61c91968-749d-4a1d-8da8-814e627e5dc1/Screenshot_2022-11-07_at_14.15.27.png)

Fill in the App name as **Baserow** and Contact email, then click the **Create app** button.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/7c267d51-8912-4fa6-bb93-d6e0ba589658/Screenshot_2022-11-07_at_14.16.51.png)

Next, log in to Baserow. Go to the Admin > Authentication > Provider. Retrieve your _**Callback URL**_ from your Baserow admin settings modal, following the [steps in this guide](/user-docs/enable-single-sign-on-sso#oauth-provider-configuration).

To be able to load this URL, add all domains and sub-domains of your app to the App Domains field in your app settings.

From the sidebar, navigate to **app products > Facebook login > settings** and add your redirect URL under **Valid OAuth Redirect URIs.** This is the Baserow Callback URL you will find in the Baserow Provider Settings where you create or edit the authentication provider.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/ffba17d9-1578-4195-9472-a242b039af04/Screenshot_2022-11-07_at_14.48.24.png)

Save your changes.

From the Facebook app dashboard, navigate to Settings → Basic.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/c1bf122c-10ff-4483-95f9-ed83199d8f60/Screenshot_2022-11-07_at_14.19.20.png)

In the app Settings > Basic, click on “Add Platform” then select “Website”. Enter the Callback URL as the Site URL(s) in the field that appears.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/f1136711-129d-4adb-8ebb-adbb6ee443ff/Screenshot_2022-11-07_at_14.26.47.png)

Then click on **Save changes**.

To integrate Baserow with Facebook,

  * Obtain App ID, this will be the Baserow Client ID.
  * Obtain App secret, this will be the Baserow Secret.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d0cf2871-a948-4e95-8739-78cdce5f9984/Screenshot_2022-11-07_at_14.28.08.png)

Set App Mode from Development to Live.

After you’ve accessed this information from the application, copy and paste the information from Facebook into Baserow.

## Connect Facebook to your Baserow Account

Head back to Baserow Admin > Authentication > Provider.

Configure Facebook by inputting the **Client ID** and **Secret** information into the corresponding fields in your Baserow Admin Dashboard, following the [steps in this guide](/user-docs/enable-single-sign-on-sso#oauth-provider-configuration).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/a2f2fc8f-6ed6-4ca0-a854-aa3f78e34807/Screenshot_2022-11-07_at_14.29.37.png)

You should be able to log in with Facebook after completing these steps by visiting your Baserow servers login page. Your users will now be taken to a Facebook sign-in flow when they attempt to log into Baserow. After logging in with their Facebook credentials, they will be redirected to the app.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/5e95edb4-e3a9-4ed1-afd4-c41baaf9e882/Screenshot_2022-11-07_at_14.30.15.png)

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

