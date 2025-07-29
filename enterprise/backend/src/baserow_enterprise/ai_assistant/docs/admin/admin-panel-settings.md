# Baserow Documentation

Source: https://baserow.io/user-docs/admin-panel-settings

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Admin panel - Settings

Instance Admins can control two fundamental aspects of their organization’s Baserow account on the Settings page of the Admin Panel: account restrictions and user deletion.

> Instance-wide Admin panel is an Enterprise-level feature. [Refer to this support article](/user-docs/enterprise-license-overview) to learn more about our Enterprise plan and the additional features it provides.

Instance Admins have admin access to the entire self-hosted instance. The controls in this section help to manage your organization’s security protocols.

## Overview

Click on the Settings option in the Admin Panel’s navigation sidebar to navigate to the **Settings** page. This will bring up a page with settings options.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/e27b5db3-a72a-4383-831a-95d504c16e05/Screenshot_2023-01-06_at_09.19.22.png)

## Account restrictions

The “Account restrictions” section allows Instance admins to control who can gain access to your organization. This setting can be adjusted by clicking the toggle to enable or disable.

### Allow creating new accounts

By default, any user visiting your Baserow domain can sign up for a new account. This setting allows Instance admins to prevent users from inviting non-users to sign up for a new account.

After [setting up a self-hosted Baserow instance](/docs/index#installation), It may be important to restrict premium access or allow non-members to view the data for a licensed workspace. You can disable the ability to sign up for a new account on the self-hosted instance URL.

To disable sign-up on self-hosted Baserow instance: Admin → Settings → Allow creating new accounts → Toggle off.

### Allow signups via workspace invitations

If you toggle off the **Allow creating new accounts** option, the “Allow signups via workspace invitations” option will appear. Instance Admins can use this setting to prevent or allow users to invite other users from outside your Enterprise domain.

Toggling this option on means that only directly invited users can create an account, so only members with workspace admin roles can invite users. For instructions on how to invite users to a workspace, [see this support article](/user-docs/manage-workspace-permissions).

> Note that even if the creation of new accounts is disabled, this option permits directly invited users to still create an account.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/04da95b5-d442-4a60-ba5e-8e14bd0b36af/Screenshot_2023-01-06_at_09.28.34.png)

### Allow resetting password

By default, users can reset their passwords. The last option in the Account restrictions section allows Instance admins to restrict users from requesting a password reset link.

> Please keep in mind that if you disable this option, you risk locking yourself out of the system and losing access to your account if you forget your password.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2127c0f1-1a7b-4f2d-9497-0e19768f8487/Screenshot_2023-01-06_at_09.38.31.png)

### Allow everyone to create new workspaces

With this setting enabled, new users will have a workspace automatically created for them where they are Workspace Admins. For billing purposes, they will be reported as Admin. Learn more about [Who is considered a “user” for billing purposes](/user-docs/subscriptions-overview#who-is-considered-a-user-for-billing-purposes) in this support article.

To prevent this, disable this setting. This will only allow staff to create new workspaces. Newly invited users will only start with the role they were invited with.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d6c4767e-a290-490a-aeb0-0cd13b0831d4/Screenshot_2023-01-13_at_09.33.10.png)

## Email verification

Email verification is a security measure that confirms the legitimacy of email addresses associated with Baserow accounts. This helps to prevent unauthorized access and ensures you’re collaborating with the intended users.

![Email verification](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/257926a7-b4d7-499e-bfd4-8d30fce31e4c/Email%20verification.png)

### Email verification levels

Baserow offers three email verification levels, allowing you to customize the verification requirement for your [collaborators](/user-docs/managing-workspace-collaborators):

  * **No verification** : Users can begin using Baserow immediately upon registration, without needing to verify their email address. This option offers the quickest onboarding experience but provides the least security. It’s suitable for low-risk workspaces with a high level of trust among collaborators.
  * **Recommended verification** : This option encourages users to verify their email address but doesn’t make it mandatory for initial use.
  * **Enforced verification** : Upon registration, a verification link is sent to the user’s email address. Verifying this email is essential to start using Baserow. This option prioritizes security and ensures all collaborators have valid email addresses. It’s ideal for workspaces handling sensitive information.

### Configure email verification

Only Baserow instance admins can modify the email verification setting. Here’s how to configure it:

  1. Navigate to the [Admin Panel](/user-docs/enterprise-admin-panel) → Settings.
  2. Scroll down to the User section → Email Verification setting.
  3. Choose your preferred verification level from the available options.

Once configured, the chosen verification level will apply to all new user registrations within your Baserow instance.

## User deletion grace delay

When you delete an account in Baserow, that account will remain on Baserow for a retention period before it’s permanently deleted.

The default grace delay period is 30 days. Instance Admins can adjust this period in the User deletion section.

Grace delay is the number of days without a login after which an account scheduled for deletion is permanently deleted.

> Note that the default grace delay period only applies when an [account is scheduled for deletion from the user’s account settings](/user-docs/delete-your-baserow-account). It does not apply when the [user is permanently deleted from the User page of the Admin panel](/user-docs/admin-panel-users#permanently-delete-a-user).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/7afc9b19-28d7-46b5-883c-6ad211fcc956/Screenshot_2023-01-06_at_10.29.58.png)

## Track workspace usage (Maintenance)

This enables a nightly job that automatically tracks workspace usage. The job calculates the total number of rows and files used within each workspace. This data is then displayed on the premium workspace admin page, providing insights into workspace activity.

If enabled, usage data is displayed on the premium workspace admin page.

If not enabled, no workspace usage data is collected or displayed on the admin page.

## Co-branding for enterprises

Baserow provides a co-branding option for Enterprise plan users. This feature allows you to upload your logo and tailor Baserow’s appearance to align with your company’s brand.

### What gets branded?

Your logo will be displayed prominently across various locations, for example:

  * Email header: Emails sent from Baserow will feature your logo at the top, reinforcing your brand identity in every communication.
  * Sidebar: Your logo will be displayed in the bottom left corner of the Baserow sidebar, providing continuous brand visibility.
  * Publicly shared views: When you [share a Baserow view publicly](/user-docs/public-sharing), your logo will be displayed, ensuring your brand recognition even outside your organization.
  * Publicly shared forms: Similar to publicly shared views, your logo will be incorporated into any forms you make public.

and other locations where the logo is displayed.

![Enterprise co-branding in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9cebfa8b-046f-4ea0-b784-9b2f433e3bf9/Co-branding%20for%20enterprises.png)

To upload a custom logo:

  1. Navigate to the Admin Panel: Click on the Admin → Settings.
  2. Access branding options: On the Admin Settings page, scroll down to the “Branding” section.
  3. Upload your logo: Locate the Logo category within the branding section. Here, you can upload your desired company logo to replace the Baserow logo with your custom alternative.

