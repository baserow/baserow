# Baserow Documentation

Source: https://baserow.io/user-docs/delete-your-baserow-account

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Delete your Baserow account

You can delete your Baserow account by visiting your Baserow account page.

## How to delete your account

  1. Log in to your account.
  2. From the Settings page, you can schedule the deletion of your account. At the bottom of the sidebar of your account page, there is an option you can click that says “Delete account.”
  3. Click **Delete account** button. If you still have an active subscription, it must be [cancelled](/user-docs/change-a-paid-subscription#cancel-a-subscription) before deleting your account.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/c2095e91-60b1-4e1d-a5aa-f492a0fa34e2/Screenshot%202022-07-22%20at%2014.43.29.png)

After you click the **Delete account** button, your account will not be deleted immediately. Your account will be scheduled to be deleted. There is a grace period before your account is permanently deleted. Your account will be permanently deleted after the grace time.

If you log in again before the grace period, your account is activated again and your account deletion will be cancelled. If you don’t log in during the grace period, your account will be permanently deleted.

> The default grace delay period is 30 days. Enterprise Admins can adjust this period in the Settings page of the Admin Panel. During the grace period, it’s still possible to access your data via the API because your account still exists. To revoke access immediately, we recommend deleting your API tokens, databases and tables, before deleting your account.

## What happens to my workspaces when I delete my account?

When your account is permanently deleted, all workspaces and associated data for which you are the last active user with Admin permissions will also be permanently deleted. The popup will show workspaces where you are the sole Admin.

If there are others who have also access to the workspace, it will not be permanently deleted. To prevent the workspace(s) from being deleted you must [transfer ownership](/user-docs/working-with-collaborators) to another user admin before deleting your account.

