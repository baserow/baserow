# Baserow Documentation

Source: https://baserow.io/user-docs/admin-panel-audit-logs

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Admin panel - Audit logs

> The audit log feature is exclusive to workspaces on the Advanced and Enterprise plans.

Baserow audit log works at instance level and at [workspace level](/user-docs/manage-workspace-permissions#workspace-level-audit-log) for SaaS Hosted Advanced and self-hosted Enterprise users.

The audit log keeps track of every action performed in your Baserow instance. You can have complete visibility into what you and your collaborators have been working on.

This allows for the detection of potential security issues and the identification of malicious attempts. Only Instance administrators have access to the Baserow audit log. Instance Admins have admin access to the entire self-hosted instance.

> Instance-wide Admin panel is an Enterprise-level feature. [Refer to this support article](/user-docs/enterprise-license-overview) to learn more about our Enterprise plan and the additional features it provides.

In this article, we’ll dig into the Audit log page of the Admin panel, and how to access and evaluate audit logs in Baserow.

## Overview

Activity log events are available for a maximum of 360 days. The audit log page of the admin panel offers a variety of tools that can output various information about

  * What **action** was executed
  * The **user’s** email address of who executed the action
  * **Date and time** when the action was executed
  * The **IP address** of the executor
  * Which **workspace** it was related to

> Activity log events are available for a maximum of 360 days.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/5dd215da-bd98-4261-931f-ee2b16e4c038/Untitled.png)

### Events in the activity log

It may be necessary for Instance Admins to audit which users have accessed or modified specific databases or workspaces. This includes events such as:

  * Create / Delete / Move / Update row
  * Create /Delete / Import / Update rows
  * Create / Delete / Order / Update workspace
  * Create / Delete / Duplicate / Update field
  * Create / Delete / Duplicate / Order / Update table
  * Create / Delete / Restore snapshot
  * Create / Delete / Duplicate / Order / Update application
  * Create / Delete / Duplicate / Order / Update view
  * Create / Delete / Update team
  * Create / Delete / Update decoration
  * Create / Update user
  * Update a view filter / a view sort / view field options
  * Create a view filter / team subject / a view sort
  * Delete a view filter / a view sort / team subject
  * Assign role
  * Cancel user deletion
  * Install template
  * Schedule user deletion
  * View slug URL updated

## Filtering logs

The Audit page in Admin Panel allows Instance admins to filter and sort log data.

To view audit logs from the UI, navigate to the Audit log page of the Admin Panel. Instance Admins can narrow a search by user, workspace, event type, or dates.

## Searching and sorting logs

From the Audit log home page, Instance admins can organise and sort log data by:

  * **User** \- Alphabetically (▾) or reverse-alphabetical order (▴)
  * **Workspace** \- Alphabetically (▾) or reverse-alphabetical order (▴)
  * **Event Type** \- Alphabetically (▾) or reverse-alphabetical order (▴)
  * **Timestamp** \- Oldest activity (▾) or most recent activity (▴)
  * **IP Address** \- Number (▾) or most (▴)

Instance Admins can sort log data by clicking on any of the column names in the header. To sort, simply click the header column that you would like to sort by.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/25329209-468d-4af0-8efd-bba89cc7d972/Screenshot_2023-01-17_at_09.56.13.png)

## Audit Log CSVs

An Instance admin can download a CSV file that contains the list of the audit logs. You can download a CSV file with the following data columns:

  * User Email
  * User ID
  * Workspace Name
  * Workspace ID
  * Action Type
  * Description
  * Timestamp
  * IP Address

> CSVs can be imported into a Baserow table and used with any supported application. Learn how to [import a CSV file into a database](/user-docs/create-a-table#import-a-csv-file-into-a-database) or how to [import a CSV file into an existing table](/user-docs/import-data-into-an-existing-table).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2f907c2f-a1f4-4f9b-88c6-2b755ce317ce/d78c8c46d16781ca57ab644abdd01601f62b0e55.webp)

When you export an audit log, the modal will show that the request is being processed, a timestamp for the most recent request, and a download link.

