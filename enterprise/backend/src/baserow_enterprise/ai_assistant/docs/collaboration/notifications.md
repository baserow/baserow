# Baserow Documentation

Source: https://baserow.io/user-docs/notifications

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Notifications

Notification is a central place where you’ll receive updates on what’s happening in your workspace. In this support article, we will cover details about notifications in Baserow.

![Notifications in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/c121d580-9411-4e37-820a-dea8fb06b0f2/Notifications.png)

## Overview

In the Notification section, you’ll find all the important updates about your workspace. Whenever someone mentions you in the comments, invites you to a workspace, or a new version is released, you’ll receive a notification. It’s a convenient way to stay informed and never miss out on any important activity.

You’ll get a notification when someone mentions you in the comments, invites you to a workspace, or when a new version of Baserow is released.

You can [get alerts when someone mentions you in a comment](/user-docs/row-commenting#track-comments) or, you can get alerts for all comments on a row, even if no one mentions you.

## View notifications

When you have unread notifications in your workspace, you’ll notice a badge displaying the number of notifications awaiting you next to the Notifications tab at the top of your side panel.

To view notifications:

  1. Click on **Notifications** in the sidebar to open a modal containing all the updates. Notifications are shown chronologically.
  2. Click on any notification to jump view the update.

Unread notifications will be conveniently highlighted with a blue dot and a distinct background color, making it easy for you to identify items that require your immediate attention.

You can also choose to **Mark all notifications as read** or **Clear all** notifications.

## Email notifications

![Baserow email notifications](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d1e9a641-ebc5-433c-a653-c88ccf77729f/Email%20notifications.png)

With Baserow email notifications delivered right to your inbox, you never have to miss an important update. You’ll receive notifications to the email address associated with your Baserow user account when:

  * Someone mentions you in a comment.
  * You’re invited to a workspace.
  * You’re added to a row as a collaborator (new feature).

To manage your email notifications,

  1. Click on the dropdown icon beside your account name in the top-right of the home screen.
  2. Click **Settings** from the dropdown menu.
  3. Click the **Email notifications** tab.

## Email notification frequency

You can customize your email notifications in your profile settings by configuring the frequency at which emails are sent to you:

  * Instantly
  * Daily
  * Weekly
  * Never

When you set your email notifications to “Daily” or “Weekly,” instead of sending you an email every time something happens, the system batches all your notifications and sends them in one email. This occurs either once a day (Daily) or once a week (Weekly).

Each email can include up to 10 notifications. If there are more than 10, you’ll see a message like “Plus x more notifications,” where “x” is the number of additional notifications.

The time you receive these emails depends on your time zone. The system is set up to send daily emails at a specific hour, and weekly emails on a specific day. Currently, every user gets their daily email at midnight UTC (Coordinated Universal Time).

If you’re self-hosting, you can change the time and day these emails are sent by adjusting the settings.

## Notifications for new form submissions

You can opt to receive notifications when someone fills out the form.

To turn on these notifications, just switch on the “receive form notifications” button found at the bottom of the form edit page. This helps you stay updated about new form entries and allows for fast responses when required.

![Email notifications for new form submissions](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/e6fa54e4-dcc8-4ba5-9675-e3f53bea5e38/Notifications.png)

### **Deactivation notifications**

Stay informed about system changes and interruptions with deactivation notifications. These notifications help you maintain smooth operations by alerting you when critical components of your workspace stop functioning properly.

There are three types of deactivation notifications:

  * **Webhook failures:** Receive alerts when a webhook becomes inactive after 4 consecutive failures. This helps you quickly identify and resolve integration issues.
  * **Payload size limits:** Get notified when webhooks can’t deliver complete data sets due to size restrictions. The system will inform you when only partial data (first 1,000 records) has been sent.
  * **Data sync interruptions:** Receive alerts when scheduled data synchronizations stop working, whether due to authentication issues, endpoint changes, or technical problems.

## Related content

  * [Row comments and mentions](/user-docs/row-commenting)
  * [Collaboration overview](/user-docs/managing-workspace-collaborators).
  * [Add workspace collaborators](/user-docs/working-with-collaborators).
  * [Manage workspace members](/user-docs/manage-workspace-permissions).
  * [Permissions overview](/user-docs/permissions-overview).

