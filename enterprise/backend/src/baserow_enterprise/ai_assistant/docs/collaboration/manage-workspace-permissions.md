# Baserow Documentation

Source: https://baserow.io/user-docs/manage-workspace-permissions

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Manage workspace members

In this guide, we’ll work through viewing, changing permissions, manage who has been invited to your workspace and who has accepted the invitation.

## Overview

You can see and control every collaborator on every workspace you’re an admin of.

From your **Members** ’ page in the workspace settings, you can view and manage the list of collaborators. You can modify their permissions, or remove collaborators, or resend invitations as needed. It is important to regularly review and update collaborator permissions to maintain proper access control.

> Baserow Advanced and Enterprise plans come with [advanced user management](/user-docs/permissions-overview) to boost data protection and privacy requirements.

## See who has access to your workspace

Once a [workspace admin](/user-docs/working-with-collaborators) has added someone to a workspace, you can review who you’ve invited and who has joined your workspace from the **Members** settings page. Workspace admins can see who has been invited or who has joined the workspace.

You can view all collaborators from a workspace in two ways:

  * From the sidebar, or
  * From workspace settings on the dashboard.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-08_at_20.50.46.png)

To see who has joined your workspace, or to see who you’ve invited,

  1. Go to **Members** settings page within the workspace.
  2. By selecting the **Members** button, you will be sent immediately to the workspace members dialog for that particular workspace.

People who are allowed to view your workspace are listed here. Check to make sure that no unauthorized persons have access to your workspace data.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-17_at_14.30.24.png)

## Update permissions in a workspace

From the workspace members page, workspace admins can control which users have access to what data. Admins can control which [default role](/user-docs/permissions-overview) each member in the workspace has.

Admins of workspaces can view and change a user’s default role. When a collaborator is updated with new permission, their access level is updated to match their new permissions.

  1. Navigate to your members’ page by clicking **Members**.
  2. Select the option to switch the user’s access.
  3. Modify a member’s default role on the workspace level by selecting an option from the default role dropdown.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/29c1effc-2e9a-44c8-8b64-ae04a63b006b/Screenshot_2023-01-18_at_17.24.14.png)

## Pending invites

The pending invites tab displays a list of people who have been invited to use Baserow but have not yet created an account.

Workspace admins can use the search box to find users by email, view the message attached to the invite, view or change the default role, and cancel all pending invitations.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/827e5fe5-401b-4e4a-bf92-347d0eeba11b/Screenshot%202023-01-05%20at%2017.43.19.png)

## Search and sort

### Search the list of collaborators

Workspace admins can do a user search by name or email to narrow their search to a single person or to include more users. A workspace admin could, for instance, look for all users whose email addresses include a specific domain name. As you search, the number of search results will show up in the search bar.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/3f6ee5bc-96ef-437e-b8cc-52f03d032d37/Screenshot%202023-01-05%20at%2017.56.45.png)

### Sort collaborators

By clicking on any of the column names in the **Members** page’s header, you can sort the results of the query.

  * Name - Alphabetically (▴) or reverse alphabetically (▾) sort users’ names.
  * Email - Alphabetically (▴) or reverse alphabetically (▾) sort users’ email addresses.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/65e2ddc7-80d9-4ead-abf0-7faceb6d8ec5/Screenshot%202023-01-05%20at%2017.55.07.png)

## Workspace-level audit log

> The audit log feature is exclusive to workspaces on the Advanced and Enterprise plans.

Baserow audit log works at [instance level](/user-docs/admin-panel-audit-logs) and at workspace level for SaaS Hosted Advanced and self-hosted Enterprise users.

The audit log keeps track of every action performed in your Baserow workspace. You can have complete visibility into what you and your collaborators have been working on.

The workspace-level audit log provides information to workspace admins about every action taken in a particular workspace.

The following information is included in each event recorded by the audit log:

  * User
  * Event type
  * From date
  * To date

Learn more about [Baserow audit logs](/user-docs/admin-panel-audit-logs).

![Workspace-level audit log](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/e072fc62-e53e-45b5-8152-d75e4bd76249/Workspace-level%20audit%20log.png)

