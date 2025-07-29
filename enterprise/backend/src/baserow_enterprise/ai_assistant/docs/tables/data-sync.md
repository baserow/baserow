# Baserow Documentation

Source: https://baserow.io/user-docs/data-sync-in-baserow

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Create a table via data sync

Data synchronization, or Data sync, ensures your information is consistent and up-to-date across multiple platforms and tables. By automating the process of updating data, you can eliminate the need for manual updates in different systems. This guarantees that everyone within your organization has access to the latest information, reducing errors and increasing efficiency.

This section will guide you through the process of setting up and managing data sync in Baserow.

For other ways to create a Baserow table, please see these articles:

  * [Start with a new table](/user-docs/create-a-table#start-with-a-new-table)
  * [Duplicate an existing table](/user-docs/create-a-table#duplicate-a-table)
  * [Paste table data](/user-docs/create-a-table-via-import#paste-table-data)
  * [Create a new table from an import](/user-docs/create-a-table-via-import).

![Image: Sync Jira, GitLab, and GitHub issues](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/920300d9-ac20-4aab-9c2a-40c4d94a1981/data_sync_jira_gitlab_github_and_postgresql.webp)

## Overview of data sync

Data sync streamlines your workflow and ensures data accuracy. By automatically updating data in real-time across multiple tools and databases, it eliminates the need for manual updates. This means you can be confident that everyone is always working with the most up-to-date information.

> Synced tables are read-only, which means you cannot edit the data directly or [edit the field type](/user-docs/baserow-field-overview). You will need to modify the data at the main source.

## How to set up data sync

Setting up data sync is simple.

  1. Navigate to the database sidebar in Baserow, and click **\+ New table**.

  2. Select the desired sync source from the available integration options.

  3. Provide the required synchronization details. For example:

     * **For iCal feed** : Enter the iCal URL (usually provided by your calendar service) in the designated field.
     * **For Baserow table** : Choose the [workspace](/user-docs/intro-to-workspaces), [database](/user-docs/intro-to-databases), and [table](/user-docs/intro-to-tables) you want to sync from.

> Learn more about the sync sources supported.

  4. Give the new table a descriptive name to identify the synced data easily. Click **Next** to proceed.

  5. Select the specific fields you want to bring into your synced table. For example, in an iCal feed, you may select to sync only event names and start/end times.

> Not all fields from an external source are required to be synced. You have the flexibility to choose only the fields relevant to your workflow, which helps to keep your workspace clean and focused.

  6. Click **Create and sync table** to establish the sync. Your table will be created, and data will start syncing from the connected source immediately.

![Screenshot of Baserow sync table](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/e1da198d-17ef-495d-9ee7-6eb1bb6d5640/screenshot_of_baserow_sync_table.webp)

## Data sync sources

Data sync in Baserow can integrate with multiple sources:

  * Sync iCal feed
  * Sync PostgreSQL table
  * Sync Baserow table
  * Sync Jira issues
  * Sync GitHub issues
  * Sync GitLab issues
  * Sync Hubspot contacts

### Sync iCal feed

iCal feed sync is designed to bring calendar data into Baserow. The iCal calendar sync synchronizes automatically with the entries in the URL’s calendar file. It only supports the ICS (Internet Calendar and Scheduling) file type.

This is particularly useful for syncing shared calendars, project timelines, or event schedules across different platforms into a single database.

### Sync PostgreSQL table

To seamlessly integrate your PostgreSQL data into Baserow, you can synchronize specific tables. This allows you to view, edit, and manage your data directly within the Baserow interface.

To initiate the synchronization process, you’ll need to provide the following information:

  * Server hostname: The address of your PostgreSQL server.
  * Username: The username used to access the database.
  * Password: The corresponding password for the specified username.
  * Database name: The name of the database containing the table you want to synchronize.
  * Schema name: The schema within the database where the table resides.
  * Table name: The exact name of the PostgreSQL table you wish to synchronize.
  * Port number: The port number used by the PostgreSQL server (default is 5432).
  * SSL mode: The desired SSL mode for the connection (e.g., ‘disable’, ‘verify-ca’, ‘require’).

When you initiate the synchronization, Baserow will initially select all rows from the specified PostgreSQL table.

To protect your sensitive data, we advise limiting the user account used for the synchronization to read-only permissions. This will prevent accidental or malicious modifications to your PostgreSQL data.

### Sync Baserow table

Baserow table sync allows you to connect and synchronize tables between different workspaces in Baserow. This integration ensures that any updates made in the original table are reflected in the synced version.

You need to upgrade your account to the [advanced/enterprise version](/user-docs/pricing-plans) to sync Baserow tables. You can upgrade your account by [getting a license](/user-docs/activate-enterprise-license).

![Screenshot to Select the fields you would like to sync](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/a2733ae8-2dad-49da-aae1-713485ab67af/screenshot_to_select_the_fields_you_would_like_to_sync.webp)

### Sync Jira issues

Baserow offers integration with Jira, allowing you to sync your issues and maintain a unified view across different teams. This eliminates the need to constantly switch between tools and manually update information on both platforms.

Here’s how to establish the connection:

  * Locate your Jira instance URL: Start by identifying the base URL of your Jira instance. This will typically resemble ‘<https://your-domain.atlassian.net>’.
  * Provide your Jira credentials: Baserow requires authentication to access your Jira data. You can authenticate using either: 
    * **Personal Access Token (recommended)** : Generate a personal access token from your Jira account settings for enhanced security and fine-grained permissions control.
    * **Username and API Token** : Enter the username (the email address you use to sign in) and the API token associated with your Jira account. To generate an API token, visit <https://id.atlassian.com/manage-profile/security/api-tokens>.
  * Specify Jira project key (Optional): If you want to synchronize issues from a specific project within Jira, enter the corresponding project key (e.g., PROJ). You can find this information by accessing the project settings within your Jira account. Leaving this field blank will result in importing all issues from your Jira instance.

The personal access token authentication method provides improved security and allows for more granular permission management compared to traditional username/password authentication.

### Sync GitHub issues

You can synchronize your GitHub issues with Baserow, ensuring everyone has access to the latest information and maintaining a single source of truth across teams.

Here’s how to establish the connection:

  * Name: Choose a clear and descriptive name for this connection to easily identify it later.
  * Owner: Locate the repository owner’s username displayed in the top left corner of your GitHub repository (typically formatted as owner/repo).
  * Repository: Enter the specific name of the GitHub repository you want to sync (also displayed in the top left corner as owner/repo).
  * API token: To grant Baserow read access to your GitHub issues, generate an API token. Visit <https://github.com/settings/tokens>, click on “Generate new token,” select “All repositories,” and under “Repository permissions,” ensure “Issues” has “read-only” access. Paste the generated token into the designated field.

### Sync GitLab issues

Seamlessly sync your GitLab issues with Baserow, maintaining a single source of truth across different teams.

Here’s how to set up the integration:

  * Base URL: Enter the base URL of your GitLab instance. For example, if you’re using [GitLab.com](http://GitLab.com), the base URL would be “<https://gitlab.com>”.
  * Project ID: Locate the project ID for the specific project containing the issues you want to sync. Open your project page in your browser (e.g., “<https://gitlab.com/baserow/baserow>”). Click the three dots menu in the top right corner and select “Copy project ID: [ID number]”. Paste the ID number into the corresponding field in Baserow.
  * Access token: To grant Baserow read access to your GitLab issues, you’ll need to generate a personal access token with “read_api” permissions. Navigate to your GitLab user settings (<https://gitlab.com/-/user_settings/personal_access_tokens>). Click “Add new token” and ensure the “read_api” scope is selected. Copy the generated token and paste it into the Baserow access token field.

### Sync HubSpot contacts

The HubSpot data sync feature allows you to automatically synchronize data between Baserow and HubSpot CRM, allowing seamless management and viewing of HubSpot contacts directly within your Baserow database.

Here’s how to set up the synchronization

  * Name: The table requires a name to help identify and organize your data.
  * Private app access token: To securely sync your HubSpot data, you must generate a private app access token from HubSpot.

To generate a private app access token:

  1. Log in to your HubSpot account.
  2. Click **Settings** in the top navigation bar.
  3. Go to Integrations > Private Apps.
  4. Create a new private app and assign the following scopes: _crm.objects.contacts.read_ , _crm.schemas.contacts.read_ , and _crm.objects.custom.read_
  5. Click **Create app** to generate the access token.

Use this token during the table setup process to establish a secure connection between HubSpot and Baserow.

![image_hubspot_data_sync](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/f5ec7571-448f-4bc4-8eca-a1feab1c430d/image_hubspot_data_sync.webp)

## Manage and update sync settings

Once a sync is established, you can easily manage and update it as needed. The [field configuration options](/user-docs/field-customization) are available. You can also [create and manage views](/user-docs/overview-of-baserow-views).

With these integrations, you can synchronize data in external platforms directly into Baserow, simplifying workflows, improving collaboration, and making data management more efficient.

### Trigger sync updates

While data sync is automated, you may need to manually trigger a sync update to synchronize data between Baserow and the source.

To pull the latest data from your connected source into Baserow,

  1. Go to the synced table in Baserow and click on the three-dot menu to open the table options.
  2. Click **Sync table**.

This will refresh the data, pulling the latest information from the main source.

During this process, a lock is placed on the updated rows, which may temporarily slow down API requests or table modifications.

![Screenshot of data sync in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/279cf13c-95fd-47e8-a8ed-16471d2e8acc/data_sync.webp)

### Periodic sync

As of Baserow 1.31 you are able to set a sync shedule within the periodic sync settings. This can be accessed through the elipsis menu of any synced table.

The default interval setting is set to “Manual” and can be changed to either “Hourly” or “Daily”

**Daily**

Daily interval syncs allow you to choose at what time the sync should occur each day. This is using a 24 hour system, so the time from the screenshot below is 4:29:18 PM.

![daily sync settings](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/user_files/O24Ax8tN1cMsz6UfGkTTxvP6rVyDVNzM_097dd28d744e7a5d6fbf0375730349211d7f60255974000afa50eb37b5c6cd42.png)

**Hourly**

The hourly interval sync allows you to set the exact minute and seconds that the sync will occur at each hour. In the screenshot below, the sync will happen every hour on the 29th minute and 18th second.

![daily sync settings](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/user_files/KshOKWGHedPZuZMyOaVcdsVwZSlNd9Xp_3be5b5805528eddf66dc95d7729fcbdf6bbdb98ff2725f0607d674c558ad8cca.png)

### Add new fields

Although synced data is read-only by default, you can [add new fields](/user-docs/adding-a-field) to the synced table to track additional information not provided by the source.

These new [fields added to the Baserow table are editable](/user-docs/field-customization) and will not interfere with the synced data.

To identify a read-only field that is part of the table’s data sync, you will see an arrow beside the synced fields and table.

![Screenshot to identify a synced field](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/1338865f-6680-4868-b330-4f2b6307c85b/screenshot_to_identify_a_synced_field.webp)

