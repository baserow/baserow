# Baserow Documentation

Source: https://baserow.io/user-docs/admin-panel-users

---


## Individual user actions

Instance Admins can access user actions by clicking the ellipses (three-dot) icon to the right of the page. By clicking this button, a list of options for modifying that user’s account will appear in a new window.

Instance admins can take the following actions:

  * Edit the name and email of a user.

  * Make the user staff: Making a user staff gives them admin access to the entire instance. This action makes the user a super admin in the Baserow instance.

> Instance Admins have server-wide access to all users and all workspaces. They have the ability to revoke another Instance Admin’s own staff permissions. The user that installs and sets up Baserow is automatically an Instance Admin and has staff privileges.

  * Change the user account password.

  * Impersonate a user. An Instance admin is unable to impersonate their own account.

  * Deactivate or activate the user’s affiliation with your organization’s Enterprise license. When a user is marked as inactive they are prevented from signing in or signing up again using the email address.

  * Delete a user.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/680319a2-dedf-4aea-a9b2-6af47bd721f5/Screenshot_2023-01-05_at_18.18.39.png)

## Make a user an Instance Admin

Instance Admins have admin access to the entire self-hosted instance. To make a user an Instance admin, they must have access to the Baserow instance.

Log in to your Baserow server as an Instance admin:

  1. In the navigation sidebar on the left side of the page, click on the **Admin** tab.
  2. Click on the **Users** tab.
  3. Click on the ellipses (three-dot) icon to the right of the user you want to make the super admin.
  4. In the auth_user table, click the **Edit** button.
  5. Set the field called `is_staff` as true ☑︎ for a user.

To remove a user as an Instance admin, set the field as false ☐.

![Baserow INSTANCE ADMIN](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/e831ef8a-37a3-400c-b4f3-a71faf60fbe4/Screenshot%202023-09-29%20at%2014.27.52.png)

> Note that making the user staff gives them admin access to all users, all workspaces, and the ability to revoke your own staff permissions.

## Search and sort the list of members

Use the search bar to find vital information quickly.

Instance Admins can do a user search by name or email to narrow their search to a single person or to include more users. An Instance admin could, for instance, look for all users whose email addresses include a specific domain name. As you search, the number of search results will show up in the search bar.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/fc5b0cf1-d490-42f3-b236-1e1e288af642/Screenshot_2023-01-05_at_17.56.45.png)

By clicking on any of the column names in the Members page’s header, you can sort the results of the member’s query.

  * **Name** \- Alphabetically (▴) or reverse alphabetically (▾) sort users’ names.
  * **Username** \- Alphabetically (▴) or reverse alphabetically (▾) sort users’ email addresses.
  * **Last login** \- Most recent (▴) or oldest login date (▾).
  * **Signed up** \- Most recently joined (▴) or oldest joined date (▾).
  * Active - Show Active first (▴) or show deactivated users first (▾).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/f5fe322f-5823-4615-815a-5f31ec431ca5/Screenshot_2023-01-05_at_18.12.16.png)

## Permanently delete a user

A user account can be deleted from the User page in the Admin Panel.

Instance Admins can permanently delete a user by clicking the ellipses (three-dot) icon to the right of the page. By clicking this button, options for that user will appear.

After clicking the “Permanently delete” button, a pop-over will display asking you to confirm that you would like to delete the user.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9fae1986-b187-4f1a-acc9-f8e1ba2667bd/Screenshot_2023-01-06_at_10.36.52.png)

## FAQs

### What happens when a user is deleted?

When a user is deleted from the User page of the Admin panel, the account is permanently deleted and cannot be recovered. The [default grace delay period](/user-docs/admin-panel-settings#user-deletion-grace-delay) does not apply.

### What happens to a user’s workspace when they are deleted?

When a user is deleted, the workspaces that the user is a member of will continue to exist. The workspace will not be deleted, even if the deleted user is the last member in the workspace. However, deleting the last user in a workspace will prevent anyone from accessing that workspace.

### Can a deleted user sign up using the same email address?

After deleting a user, it’s possible for a new user to sign up using the same email address. To prevent this, it’s recommended to deactivate the user instead of deleting them. This ensures that the deleted user cannot sign up again using their previous email address.

### What is the difference between deleting a user and revoking workspace access?

It’s important to understand the differences between [removing users from a workspace](/user-docs/remove-a-user-from-a-workspace), table, or database and permanently deleting a user account from a self-hosted instance.

In the SaaS hosted and self-hosted versions, admins can remove a member from a workspace, table, or database. Removing a user from a workspace, table, or database means their access to that specific application is revoked, but their account remains unaffected.

In the self-hosted version, Instance Admins have the ability to permanently delete a user from the entire self-hosted instance. This means that when a user is deleted from the User page in the Admin panel, their account is permanently removed and cannot be recovered.

## Related content

  * [Enterprise admin panel](/user-docs/admin-panel-workspaces).
  * [Admin panel - Workspaces](/user-docs/admin-panel-workspaces).
  * [Admin panel - Audit logs](/user-docs/admin-panel-audit-logs).
  * [Admin panel - Settings](/user-docs/admin-panel-settings).
  * [Activate Enterprise license](/user-docs/activate-enterprise-license).

