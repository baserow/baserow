# Baserow Documentation

Source: https://baserow.io/user-docs/export-workspaces

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Export a workspace

Welcome to our guide on exporting workspaces in Baserow. Whether you’re transferring your data between Baserow instances, sharing your workspace with others, or creating a secure offline backup, we’re here to help you every step of the way.

In this guide, we’ll walk you through the process of exporting your workspaces and how you can manage the data effectively.

![image: Export and import of workspaces](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/df1de900-ae61-4ab5-a9ff-197a9a8ddbd8/export_and_import_of_workspaces.webp)

## Overview

Exporting workspaces is a convenient way to ensure your data is portable and secure. This allows you to:

  * Transfer your data between different Baserow instances seamlessly.
  * Copy data between workspaces for collaborative or testing purposes.
  * Create offline backups for added security or archiving.

By exporting workspaces, you maintain control over your data and keep it accessible wherever and whenever you need it.

> Note that an export will not include any [permissions](/user-docs/permissions-overview) set on the application and its tables.

## How to export a workspace

Exporting a workspace in Baserow is straightforward. Here’s how you can do it:

  1. Navigate to the Home page: Start by clicking on the ‘Home’ tab in the top navigation menu. This will take you to a list of all your workspaces.
  2. Locate the workspace you want to export. Next to the workspace name, you’ll see a small arrow icon. Click on this icon to open the dropdown menu.
  3. In the dropdown menu, look for and click the option labeled ‘Export data’. This action initiates the export process.
  4. Enable “Export structure only” to export only the structure of the application. Otherwise, leave blank to include the data on export.
  5. Once the export process is completed, a downloadable file will be created. Save this file securely, as it contains all the data from the selected workspace.

After you export the workspace, the file you download will be found in your device’s default download folder. Your data will be exported as a ZIP file, which can be imported into other Baserow instances.

Workspace exports may contain sensitive information. Store them in a secure location with restricted access.

## Import data into Baserow

After exporting a workspace, you might want to import it into another Baserow instance. The import process complements exporting and makes transferring data efficient.

  * Navigate to the target instance where you want to import the data.
  * Use the ‘Import data’ option available in the menu and upload the exported file.
  * Confirm the import to ensure the data is correctly loaded into the workspace.

Find out how to [import data into a database](/user-docs/import-workspaces) or [table](/user-docs/import-data-into-an-existing-table) in the support articles.

## Related content

  * [Create a workspace](/user-docs/setting-up-a-workspace).
  * [Create a table via import](/user-docs/create-a-table-via-import).
  * [Import data into an existing table](/user-docs/import-data-into-an-existing-table).
  * [Delete a workspace](/user-docs/delete-a-workspace).

